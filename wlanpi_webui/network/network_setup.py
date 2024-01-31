import json

import requests
from flask import current_app, redirect, render_template, request

from wlanpi_webui.network import bp
from wlanpi_webui.utils import is_htmx, systemd_service_message


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
                    "key_mgmt": form_data.get("key_mgmt"),
                    "eap": form_data.get("eap"),
                    "anonymous_identity": form_data.get("anonymous_identity"),
                    "identity": form_data.get("identity"),
                    "password": form_data.get("password"),
                    "ca_cert": form_data.get("ca_cert"),
                    "phase2": form_data.get("phase2"),
                    "ieee80211w": int(form_data.get("ieee80211w")),
                    "priority": int(form_data.get("priority")),
                },
                "removeAllFirst": (
                    True if form_data.get("removeAllFirst") == "true" else False
                ),
            }
        except Exception as e:
            return f"Fail: {e}"

        result = set_network(body)

        try:
            result = json.loads(result)
        except:
            pass

        messages.append(result)

    result = get_interfaces()

    try:
        result = json.loads(result)
    except:
        return "Error"

    interfaces = []

    for interface in result["interfaces"]:
        interfaces.append(interface["interface"])

    if is_htmx(request):
        return render_template(
            "/partials/network_setup.html", interfaces=interfaces, messages=messages
        )
    else:
        return render_template(
            "/extends/network_setup.html", interfaces=interfaces, messages=messages
        )


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
        if ("\0" in network["ssid"]) or (network["ssid"] in [" ", ""]):
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
                    "wpa": network["wpa"],
                    "wpa2": network["wpa2"],
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
    }

    current_app.logger.info("calling network scan on interface %s", interface)
    try:
        start_url = "http://127.0.0.1:31415/api/v1/network/network/scan"
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
            current_app.logger.info("%s generated %s response", start_url, response)
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
        start_url = "http://127.0.0.1:31415/api/v1/network/network/set"
        response = requests.post(start_url, headers=headers, json=body)
        if response.status_code != 200:
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
            )
            current_app.logger.info("%s generated %s response", start_url, response)
        current_app.logger.info("%s generated %s response", start_url, response)
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
        start_url = "http://127.0.0.1:31415/api/v1/network/network/getInterfaces"
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
