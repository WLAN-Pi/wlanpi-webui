import json
import time
import requests
from flask import current_app, redirect, render_template, request

from wlanpi_webui.network import bp
from wlanpi_webui.utils import (is_htmx, start_stop_service,
                                system_service_running_state,
                                systemd_service_message, wlanpi_core_warning)


@bp.route("/network/setup", methods=("GET", "POST"))
def netSetup():
    messages = []
    if request.method == "POST":
        form_data = request.form

        try:
            body = {
                "interface": form_data.get("interface"),
                "netConfig": {
                    "ssid": form_data.get("ssid"),
                    "psk": form_data.get("psk"),
                    "proto": form_data.get("proto"),
                    "key_mgmt": form_data.get("key_mgmt"),
                    "ieee80211w": int(form_data.get("ieee80211w")),
                },
                "removeAllFirst": (
                    True if form_data.get("removeAllFirst") == "true" else False
                ),
            }
        except Exception as e:
            return f"Fail: {e}"

        set_result = set_network(body)

        try:
            set_json = json.loads(set_result)
        except:
            pass

        messages.append(set_json)


    interfaces_result = get_interfaces()

    try:
        interfaces_json = json.loads(interfaces_result)
    except Exception as e:
        return f"Error {e}"


    
    try:
        if interfaces_json:
            interfaces = []
            for interface in interfaces_json["interfaces"]:
                interfaces.append(interface["interface"])

        if is_htmx(request):
            return render_template(
                "/partials/network_setup.html", interfaces=interfaces, messages=messages
            )
        else:
            return render_template(
                "/extends/network_setup.html", interfaces=interfaces, messages=messages
            )
    except Exception as e:
        return f"Error {e}"
    
    
@bp.route("/wpa_supplicant/setup")
def wpa_supplicant_setup():
    if is_htmx(request):
        supplicant_message = systemd_service_message("wpa_supplicant@wlan0.service")
        supplicant_status = system_service_running_state("wpa_supplicant@wlan0.service")
        supplicant_task_url = "/wpa_supplicant/startstop"
        if supplicant_status:
            # active
            supplicant_task_anchor_text = "STOP"
        else:
            # not active
            supplicant_task_anchor_text = "START"
        args = {
            "supplicant_message": supplicant_message,
            "supplicant_task_url": supplicant_task_url,
            "supplicant_task_anchor_text": supplicant_task_anchor_text,
        }
        if supplicant_status:
            # active
            html = """
            <button class="uk-button uk-button-default" uk-tooltip="wpa_supplicant@wlan0.service is in the correct mode. Stop to restore default supplicant behaviour" 
                hx-get="{supplicant_task_url}"
                hx-trigger="click delay:0.2s"
                hx-swap="outerHTML"
                hx-indicator=".progress">{supplicant_task_anchor_text}</button>
            """.format(
                **args
            )
        else:
            # not active
            html = """
            <button class="uk-button uk-button-default" uk-tooltip="wpa_supplicant@wlan0.service must be running before attempting to connect to a network." 
                hx-get="{supplicant_task_url}"
                hx-trigger="click delay:0.2s"
                 hx-swap="outerHTML"
                hx-indicator=".progress">{supplicant_task_anchor_text}</button>
            """.format(
                **args
            )
        return html


@bp.route("/wpa_supplicant/startstop")
def wpa_supplicant_startstop():
    if is_htmx(request):
        supplicant_message = systemd_service_message("wpa_supplicant@wlan0.service")
        supplicant_status = system_service_running_state("wpa_supplicant@wlan0.service")
        supplicant_task_url = "/wpa_supplicant/startstop"
        if supplicant_status:
            # active
            start_stop_service("stop", "wpa_supplicant@wlan0.service")
            time.sleep(1)
            start_stop_service("start", "wpa_supplicant.service")
            supplicant_task_anchor_text = "START"
            supplicant_tooltip = "wpa_supplicant@wlan0.service must be running before attempting to connect to a network."
        else:
            # not active
            start_stop_service("stop", "wpa_supplicant.service")
            time.sleep(1)
            start_stop_service("start", "wpa_supplicant@wlan0.service")
            supplicant_task_anchor_text = "STOP"
            supplicant_tooltip = "wpa_supplicant@wlan0.service is in the correct mode. Stop to restore default supplicant behaviour"
        args = {
            "supplicant_message": supplicant_message,
            "supplicant_task_url": supplicant_task_url,
            "supplicant_task_anchor_text": supplicant_task_anchor_text,
            "supplicant_tooltip": supplicant_tooltip,
        }
        if supplicant_status:
            # active
            html = """
            <button class="uk-button uk-button-default" uk-tooltip="{supplicant_tooltip}" 
                hx-get="{supplicant_task_url}"
                hx-trigger="click delay:0.2s"
                hx-swap="outerHTML"
                hx-indicator=".progress"
                hx-on::after-settle=window.location.reload()>{supplicant_task_anchor_text}</button>
            """.format(
                **args
            )
        else:
            # not active
            html = """
            <button class="uk-button uk-button-default" uk-tooltip="{supplicant_tooltip}" 
                hx-get="{supplicant_task_url}"
                hx-trigger="click delay:0.2s"
                hx-swap="outerHTML"
                hx-indicator=".progress"
                hx-on::after-settle=window.location.reload()>{supplicant_task_anchor_text}</button>
            """.format(
                **args
            )
        return html




@bp.route("/network/getscan")
def getscan():
    netScan = get_wifi_scan("wlan0")

    try:
        netScan = json.loads(netScan)
        print(netScan)
    except:
        return "Error"

    grouped_scan = []
    unique_ssids = []

    for network in netScan["nets"]:
        if ("\0" in network["ssid"]) or (network["ssid"] in [' ', ""]):
            network["ssid"] = "<hidden>"
        if not network["ssid"] in unique_ssids:
            unique_ssids.append(network["ssid"])

    idx = 0
    for ssid in unique_ssids:
        grouped_scan.append({"ssid": ssid, "scan": []})
        for network in netScan["nets"]:
            if network["ssid"] == ssid:
                scan = {
                    "bssid": network["bssid"],
                    "key_mgmt": network["key_mgmt"],
                    "signal": network["signal"],
                    "freq": network["freq"],
                }
                grouped_scan[idx]["scan"].append(scan)
        idx += 1

    return render_template(
        "netscan_iframe.html", netScan=netScan, groupedScan=grouped_scan
    )


def get_wifi_scan(interface):
    """
    Makes a request to do a wifi scan and returns the scan using wlanpi-core.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }
    params = {
        "type": "active",
        "interface": f"{interface}",
        "timeout": 20
    }

    current_app.logger.info("calling network scan on interface %s", interface)
    try:
        start_url = "http://127.0.0.1:31415/api/v1/network/wlan/scan"
        response = requests.get(
            start_url,
            params=params,
            headers=headers,
        )
        if response.status_code != 200:
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
            )
            current_app.logger.info(
                "error: %s",
                response.content,
            )
            current_app.logger.info("%s generated %s response", start_url, response)
            return response.content
        current_app.logger.info("%s generated %s response", start_url, response)
        return json.dumps(response.json())
    except requests.exceptions.RequestException:
        current_app.logger.exception("requests error")
        return redirect(request.referrer)


def set_network(body):
    """
    Takes the body from a form and sets the network using wlanpi-core.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }

    current_app.logger.info("setting network with params: %s", body)
    try:
        start_url = "http://127.0.0.1:31415/api/v1/network/wlan/set"
        response = requests.post(start_url, headers=headers, json=body)
        if response.status_code != 200:
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
            )
            current_app.logger.info("%s generated %s response", start_url, response.content)
        current_app.logger.info("%s generated %s response", start_url, response.content)
        return response.content
    except requests.exceptions.RequestException:
        current_app.logger.exception("requests error")
        return redirect(request.referrer)


def get_interfaces():
    """
    Gets all the interfaces using wlanpi-core.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }

    current_app.logger.info("getting interfaces")
    try:
        start_url = "http://127.0.0.1:31415/api/v1/network/wlan/getInterfaces"
        response = requests.get(
            start_url,
            headers=headers,
        )
        if response.status_code != 200:
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
            )
            current_app.logger.info("%s generated %s response", start_url, response)
        current_app.logger.info("%s generated %s response", start_url, response)
        return json.dumps(response.json())
    except requests.exceptions.RequestException:
        current_app.logger.exception("requests error")
        return redirect(request.referrer)
