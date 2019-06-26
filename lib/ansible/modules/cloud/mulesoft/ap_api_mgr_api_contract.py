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
module: ap_api_mgr_contract

short_description: Manage API Contracts on Anypoint API Manager

version_added: "2.8"

description:
    - "This module supports management of contracts over managed APIs at Environment level on Anypoint API Manager"

options:
    name:
        description:
            - API Instance ID
        required: true
    state:
        description:
            - Assert the state of the application. Use Use C(present) to create an application and C(absent) to delete it.
        required: true
        choices: [ "present", "revoked", absent" ]
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
    application_id:
        description:
            - API ID to establish the contract

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating an API Contract
- name: create an API contract
  ap_api_mgr_contract:
    bearer": "00077d85-0dd7-4ee6-a63c-beb84080558f"
    name: "15722837"
    state: "present"
    organization: "My Demos"
    environment: "Sandbox"
    application_id: "245525"

# Example of revoking an API Contract
- name: revoke an API contract
  ap_api_mgr_contract:
    bearer": "00077d85-0dd7-4ee6-a63c-beb84080558f"
    name: "15722837"
    state: "revoked"
    organization: "My Demos"
    environment: "Sandbox"
    application_id: "245525"

# Example of deleting an API Contract
- name: delete an API contract
  ap_api_mgr_contract:
    bearer": "00077d85-0dd7-4ee6-a63c-beb84080558f"
    name: "15722837"
    state: "absent"
    organization: "My Demos"
    environment: "Sandbox"
    application_id: "245525"
'''

RETURN = '''
id:
    description: API contract id
    type: string
    returned: success
status:
    description: API contract status
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


def get_apim_url(module):
    return 'https://' + module.params['host'] + '/apimanager/api/v1/organizations/' + module.params['organization_id']


def get_exchange_url(module):
    return 'https://' + module.params['host'] + '/exchange/api/v1/organizations/' + module.params['organization_id']


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


def get_ap_url_with_environment(plain_url, env_id):
    return plain_url + '/environments/' + env_id


def get_api_info(module, env_id):
    my_url = get_ap_url_with_environment(get_apim_url(module), env_id) + '/apis/' + module.params['name']
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    return execute_http_call(module, my_url, 'GET', headers, None)


def get_api_contracts(module, env_id):
    my_url = get_ap_url_with_environment(get_apim_url(module), env_id) + '/apis/' + module.params['name'] + '/contracts'
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    return execute_http_call(module, my_url, 'GET', headers, None)


def get_context(module):
    return_value = dict(
        do_nothing=False,
        env_id=None,
        contract_id=None,
        contract_status=None
    )
    url = None

    return_value['env_id'] = get_environment_id(module)
    client_list = json.load(get_api_contracts(module, return_value['env_id']))['contracts']

    for item in client_list:
        if (str(item['applicationId']) == module.params['application_id']):
            return_value['contract_id'] = str(item['id'])
            return_value['contract_status'] = item['status']
            break

    if (module.params['state'] == 'present'):
        return_value['do_nothing'] = (return_value['contract_id'] is not None) and (return_value['contract_status'] == 'APPROVED')
    elif (module.params['state'] == 'revoked'):
        return_value['do_nothing'] = (return_value['contract_id'] is None) or (return_value['contract_status'] == 'REVOKED')
    elif (module.params['state'] == 'absent'):
        return_value['do_nothing'] = (return_value['contract_id'] is None)

    return return_value


def modify_contract_status(module, context, operation):
    if (operation != 'restore') and (operation != 'revoke'):
        module.fail_json(msg='Wrong operation over XAPI (' + operation + ')')
    return_value = dict(
        msg=None,
        contract_id=None,
        contract_status=None
    )
    xapi_url = 'https://' + module.params['host'] + '/apimanager/xapi/v1/organizations/' + module.params['organization_id']
    my_url = (get_ap_url_with_environment(xapi_url, context['env_id']) +
              '/apis/' + module.params['name'] + '/contracts/' + context['contract_id']) + '/' + operation
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {}
    execute_http_call(module, my_url, 'POST', headers, json.dumps(payload))
    return_value['contract_id'] = context['contract_id']
    if (operation == 'revoke'):
        return_value['contract_status'] = 'REVOKED'
        return_value['msg'] = 'API Contract for API "' + module.params['name'] + '" revoked.'
    elif (operation == 'restore'):
        return_value['contract_status'] = 'APPROVED'
        return_value['msg'] = 'API Contract for API "' + module.params['name'] + '" approved.'

    return return_value


def restore_contract(module, context):
    return modify_contract_status(module, context, 'restore')


def create_or_approve_contract(module, context):
    return_value = dict(
        msg=None,
        contract_id=None,
        contract_status=None
    )
    if (context['contract_id'] is not None and context['contract_status'] == 'REVOKED'):
        output = restore_contract(module, context)
    else:
        my_url = (get_exchange_url(module) + '/applications/' + module.params['application_id']) + '/contracts'
        headers = {
            'Authorization': 'Bearer ' + module.params['bearer'],
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        api_info = json.load(get_api_info(module, context['env_id']))
        payload = {
            'apiId': module.params['name'],
            'environmentId': context['env_id'],
            'acceptedTerms': True,
            'organizationId': module.params['organization_id'],
            'groupId': api_info['groupId'],
            'assetId': api_info['assetId'],
            'version': api_info['assetVersion'],
            'versionGroup': api_info['productVersion']
        }
        output = json.load(execute_http_call(module, my_url, 'POST', headers, json.dumps(payload)))

    return_value['msg'] = 'API Contract for API "' + module.params['name'] + '" approved.'
    return_value['contract_id'] = output['id']
    return_value['contract_status'] = output['status']

    return return_value


def revoke_contract(module, context):
    return modify_contract_status(module, context, 'revoke')


def delete_contract(module, context):
    return_value = dict(
        msg=None,
        contract_id=None,
        contract_status=None
    )
    my_url = (get_ap_url_with_environment(get_apim_url(module), context['env_id']) +
              '/apis/' + module.params['name'] + '/contracts/' + context['contract_id'])
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    if (context['contract_status'] != 'REVOKED'):
        # I can only delete revoked contracts
        revoke_contract(module, context)

    execute_http_call(module, my_url, 'DELETE', headers, None)
    return_value['msg'] = 'API Contract for API "' + module.params['name'] + '" deleted.'

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "revoked", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=False),
        environment=dict(type='str', required=False, default='Sandbox'),
        application_id=dict(type='str', required=True)
    )

    result = dict(
        changed=False,
        contract_id=None,
        contract_status=None,
        msg='No action taken'
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

    result['id'] = context['contract_id']
    result['status'] = context['contract_status']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    if (module.params['state'] == 'present'):
        output = create_or_approve_contract(module, context)
    elif (module.params['state'] == 'revoked'):
        output = revoke_contract(module, context)
    elif (module.params['state'] == 'absent'):
        output = delete_contract(module, context)

    result['changed'] = True
    result['id'] = output['contract_id']
    result['status'] = output['contract_status']
    result['msg'] = output['msg']

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
