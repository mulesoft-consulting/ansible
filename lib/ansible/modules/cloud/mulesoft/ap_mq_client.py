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
module: ap_mq_client

short_description: Manage Clients on Anypoint MQ

version_added: "2.8"

description:
    - "This module supports management of clients at Environment level on Anypoint MQ"

options:
    name:
        description:
            - MQ Client name
        required: true
    state:
        description:
            - Assert the state of the application. Use Use C(present) to create an application and C(absent) to delete it.
        required: true
        choices: [ "present", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    organization:
        description:
            - Anypoint Platform Organization Name to work on
        required: true
    organization_id:
        description:
            - Anypoint Platform Organization ID. Default value retrieved based on organization
        required: false
    environment:
        description:
            - Environment on the Business Group to work on
        required: false
        default: Sandbox

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating an MQ client application
- name: create an exchange application
  ap_exchange_application:
    name: 'My App'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'

# Example of deleting an MQ client application
- name: delete an exchange application
  ap_exchange_application:
    name: 'My App'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
'''

RETURN = '''
mq_client_app_id:
    description: Application id
    type: string
    returned: success
mq_client_app_client_id:
    description: Application id
    type: string
    returned: success
mq_client_app_client_secret:
    description: Application id
    type: string
    returned: success
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_mq_url(module):
    return 'https://' + module.params['host'] + '/mq/admin/api/v1/organizations/' + module.params['organization_id']


def execute_http_call(module, url, method, headers, payload):
    return_value = None
    try:
        if (headers is not None):
            if (payload is not None):
                return_value = open_url(url, method=method, headers=headers, data=payload)
            else:
                return_value = open_url(url, method=method, headers=headers)

    except Exception as e:
        module.fail_json(msg=str(e))

    return return_value


def get_org_id(module):
    org_id = None
    my_url = 'https://' + module.params['host'] + '/accounts/api/profile'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))
    for item in output['memberOfOrganizations']:
        if (item['name'] == module.params['organization']):
            org_id = item['id']
            break
    if (org_id is None):
        module.fail_json(msg='Business Group {' + module.params['organization'] + '} not found')

    return org_id


def get_environment_id(module):
    env_id = None
    my_url = 'https://' + module.params['host'] + '/accounts/api/organizations/' + module.params['organization_id'] + '/environments'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    output = json.load(execute_http_call(module, my_url, 'GET', headers, None))

    for item in output['data']:
        if (item['name'] == module.params['environment']):
            env_id = item['id']
            break
    if (env_id is None):
        module.fail_json(msg='Environment {' + module.params['environment'] + '} not found onBusiness Group {' + module.params['organization'] + '}')

    return env_id


def get_mq_env_url(module, env_id):
    return get_mq_url(module) + '/environments/' + env_id


def get_existing_clients(module, env_id):
    my_url = get_mq_env_url(module, env_id) + '/clients'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    return execute_http_call(module, my_url, 'GET', headers, None)


def get_context(module):
    return_value = dict(
        do_nothing=False,
        env_id=None,
        mq_client_app_id=None,
        mq_client_app_client_id=None,
        mq_client_app_client_secret=None
    )
    app_exists = False
    url = None
    description = None

    return_value['env_id'] = get_environment_id(module)
    client_list = json.load(get_existing_clients(module, return_value['env_id']))

    for item in client_list:
        if (item['name'] == module.params['name']):
            return_value['mq_client_app_id'] = item['clientId']
            return_value['mq_client_app_client_id'] = item['clientId']
            return_value['mq_client_app_client_secret'] = item['clientSecret']
            break

    if (module.params['state'] == 'present'):
        return_value['do_nothing'] = (return_value['mq_client_app_id'] is not None)
    elif (module.params['state'] == 'absent'):
        return_value['do_nothing'] = (return_value['mq_client_app_id'] is None)

    return return_value


def create_mq_client(module, context):
    return_value = dict(
        msg=None,
        mq_client_app_id=None,
        mq_client_app_client_id=None,
        mq_client_app_client_secret=None
    )
    my_url = get_mq_env_url(module, context['env_id']) + '/clients'
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer'],
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        'name': module.params['name']
    }
    output = json.load(execute_http_call(module, my_url, 'PUT', headers, json.dumps(payload)))

    return_value['msg'] = 'MQ Client "' + module.params['name'] + '" created.'
    return_value['mq_client_app_id'] = output['clientId']
    return_value['mq_client_app_client_id'] = output['clientId']
    return_value['mq_client_app_client_secret'] = output['clientSecret']

    return return_value


def delete_mq_client(module, context):
    return_value = dict(
        msg=None,
        mq_client_app_id=None,
        mq_client_app_client_id=None,
        mq_client_app_client_secret=None
    )
    my_url = get_mq_env_url(module, context['env_id']) + '/clients/' + context['mq_client_app_id']
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    execute_http_call(module, my_url, 'DELETE', headers, None)
    return_value['msg'] = 'MQ Client "' + module.params['name'] + '" deleted.'

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=False),
        environment=dict(type='str', required=False, default='Sandbox')
    )

    result = dict(
        changed=False,
        msg='No action taken',
        mq_client_app_id=None,
        mq_client_client_id=None,
        mq_client_client_secret=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    if (module.params['organization_id'] is None):
        module.params['organization_id'] = get_org_id(module)

    context = get_context(module)

    result['mq_client_app_id'] = context['mq_client_app_id']
    result['mq_client_app_client_id'] = context['mq_client_app_client_id']
    result['mq_client_app_client_secret'] = context['mq_client_app_client_secret']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    if (module.params['state'] == 'present'):
        output = create_mq_client(module, context)
    elif (module.params['state'] == 'absent'):
        output = delete_mq_client(module, context)

    result['changed'] = True
    result['mq_client_app_id'] = output['mq_client_app_id']
    result['mq_client_app_client_id'] = output['mq_client_app_client_id']
    result['mq_client_app_client_secret'] = output['mq_client_app_client_secret']
    result['msg'] = output['msg']

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
