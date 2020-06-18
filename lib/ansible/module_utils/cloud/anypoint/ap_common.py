#!/usr/bin/python

# Copyright: (c) 2020, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.urls import open_url

def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def execute_anypoint_cli(caller, module, cmd):
    result = module.run_command(cmd)
    if result[0] != 0:
        module.fail_json(msg=caller + ' ' + result[1].replace('\n', ''))

    return result[1]


def execute_http_call(caller, module, url, method, headers, payload):
    return_value = None
    try:
        if (headers is not None):
            if (payload is not None):
                return_value = open_url(url, method=method, headers=headers, data=json.dumps(payload))
            else:
                return_value = open_url(url, method=method, headers=headers)
        else:
            module.fail_json(msg=caller + ' Can not execute an HTTP call without headers')

    except Exception as e:
        module.fail_json(msg=caller + ' Error executing HTTP call ' + method + ' to ' + url + ' [' + str(e) + ']')

    return return_value