#!/usr/bin/env python3
import json
import argparse
import os
from glob import glob
from functools import partial
import subprocess
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from copy import deepcopy

# UID for the folder under which our dashboards will be setup
DEFAULT_FOLDER_UID = '70E5EE84-1217-4021-A89E-1E3DE0566D93'

def grafana_request(endpoint, token, path, data=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    method = 'GET' if data is None else 'POST'
    req = Request(f'{endpoint}/api{path}', headers=headers, method=method)
    if not isinstance(data, bytes):
        data = json.dumps(data).encode()
    with urlopen(req, data) as resp:
        return json.load(resp)


def ensure_folder(name, uid, api):
    try:
        return api(f'/folders/{uid}')
    except HTTPError as e:
        if e.code == 404:
            # We got a 404 in
            folder = {
                'uid': uid,
                'title': name
            }
            return api('/folders', folder)
        else:
            raise



def build_dashboard(dashboard_path):
    return json.loads(subprocess.check_output([
        'jsonnet', '-J', 'vendor',
        dashboard_path
    ]).decode())


def layout_dashboard(dashboard):
    """
    Automatically layout panels.

    - Default to 12x10 panels
    - Reset x axes when we encounter a row
    - Assume 24 unit width

    Grafana's autolayout is not available in the API, so we
    have to do thos.
    """
    # Make a copy, since we're going to modify this dict
    dashboard = deepcopy(dashboard)
    cur_x = 0
    cur_y = 0
    for panel in dashboard['panels']:
        pos = panel['gridPos']
        pos['h'] = pos.get('h', 10)
        pos['w'] = pos.get('w', 12)
        pos['x'] = cur_x
        pos['y'] = cur_y

        cur_y += pos['h']
        if panel['type'] == 'row':
            cur_x = 0
        else:
            cur_x = (cur_x + pos['w']) % 24

    return dashboard

def deploy_dashboard(dashboard_path, folder_uid, api):
    data = {
        'dashboard': layout_dashboard(build_dashboard(dashboard_path)),
        'folderId': folder_uid,
        'overwrite': True
    }
    api('/dashboards/db', data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dashboards_dir', help='Directory of jsonnet dashboards to deploy')
    parser.add_argument('grafana_url', help='Grafana endpoint to deploy dashboards to')
    parser.add_argument('--folder-name', default='JupyterHub Default Dashboards', help='Name of Folder to deploy to')
    parser.add_argument('--folder-uid', default=DEFAULT_FOLDER_UID, help='UID of grafana folder to deploy to')

    args = parser.parse_args()

    grafana_token = os.environ['GRAFANA_TOKEN']

    api = partial(grafana_request, args.grafana_url, grafana_token)
    folder = ensure_folder(args.folder_name, args.folder_uid, api)

    for dashboard in glob(f'{args.dashboards_dir}/*.jsonnet'):
        deploy_dashboard(dashboard, folder['id'], api)

if __name__ == '__main__':
    main()