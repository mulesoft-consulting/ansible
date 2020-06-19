#!/usr/bin/python

# Copyright: (c) 2019, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ap_auth

short_description: Create an Anypoint Platform session

version_added: "2.8"

description:
    - "Obtain a session access token (bearer) using username and password"

options:
    name:
        description:
            - Anypoint Platform user
        required: true
    password:
        description:
            - Anypoint Platform password
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com

author:
    - Gonzalo Camino (@gonzalo-camino)
'''

EXAMPLES = '''
- name: Get access token doing a login with username and password
  session:
    name: bruce
    password: wayne
'''

RETURN = '''
access_token:
    description: The bearer token obtained from Anypoint Platform
    type: str
    returned: success
msg:
    description: The output message that the module generates
    type: str
    returned: always
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cloud.anypoint import ap_common


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        password=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com')
    )

    result = dict(
        changed=False,
        access_token='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # main Module Logic
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/login'
    my_url = server_name + api_endpoint

    headers = {'Content-Type': 'application/json'}
    payload = {"username": module.params['name'], "password": module.params['password']}

    #try:
    #    resp = open_url(my_url, method="POST", headers=headers, data=json.dumps(payload))
    #except Exception as e:
    #    module.fail_json(msg=str(e))

    #resp_json = json.loads(resp.read())
    resp_json = ap_common.execute_http_call('[run_module]', module, my_url, 'POST', headers, payload)
    result['access_token'] = resp_json["access_token"]
    result['message'] = 'Authenticated'
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
