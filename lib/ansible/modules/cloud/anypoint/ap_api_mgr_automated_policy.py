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
module: ap_api_mgr_automated_policy

short_description: Manage automated policies on API Manager

version_added: "2.8"

description:
    - "This module supports basic operations for applying and removing automated policies on Anypoint Platform API Manager"

options:
    name:
        description:
            - The policy Id on Anypoint Platform
        required: true
    state:
        description:
            - Assert the state of the managed API. Use C(present) to apply a policy over an API, C(enabled) to enable an existing policy,
              C(disabled) to disable it and C(absent) to remove it.
        required: true
        choices: [ "present", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session.
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation.
        required: false
        default: anypoint.mulesoft.com
    organization_id:
        description:
            - Anypoint Platform Organization ID to work on.
        required: true
    environment_id:
        description:
            - Environment ID on the Organization to work on.
            - Required only for C(present) state
        required: false
        default: Sandbox
    group_id:
        description:
            - Mule 4 policy group ID.
            - If no value is provided, this value defaults to MuleSoft group ID (68ef9520-24e9-4cf2-b2f5-620025690913).
        required: false
    version:
        description:
            - Mule 4 policy version.
            - Required only for C(present) state
        required: false
    configuration_data_path:
        description:
            - Pass the file path with the configuration data as a JSON string.
            - Required only for C(present) state
        required: false
    pointcut_data_path:
        description:
            - Pass the file path with the pointcut data as JSON strings.
        required: false

author:
    - Gonzalo Camino (@gonzalo-camino)


'''

EXAMPLES = '''
# Example of a creating an automated policy
- name: Apply automated policy
  ap_api_mgr_automated_policy:
    name: 'client-id-enforcement'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization_id: '8af46d8f-62ae-4181-8b19-512878257837'
    environment_id: 'b21835bb-a320-434d-87c8-d4e15fc1a212'
    version: '1.1.8'
    configuration_data_path: '/tmp/config.json'

# Example of a removing an automated policy
- name: Remove an automated policy from a managed API
  ap_api_mgr_automated_policy:
    name: 'client-id-enforcement'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization_id: '8af46d8f-62ae-4181-8b19-512878257837'
    environment_id: 'b21835bb-a320-434d-87c8-d4e15fc1a212'
'''

RETURN = '''
id:
    description: Automated Policy ID
    type: str
    returned: success
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


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


def get_apim_automated_policies_url(module):
    url = 'https://' + module.params['host'] + '/apimanager/api/v1/organizations/' + module.params['organization_id']
    url += '/automated-policies'

    return url


def get_applied_policies(module):
    return_value = []
    my_url = get_apim_automated_policies_url(module) + '?environmentId=' + module.params['environment_id']
    # use xAPI to list existing policies
    my_url = my_url.replace('/apimanager/api/v1', '/apimanager/xapi/v1')
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    output = execute_http_call('[get_applied_policies]', module, my_url, 'GET', headers, None)
    resp_json = json.loads(output.read())
    return_value = resp_json.get('automatedPolicies')

    return return_value


def read_policy_configuration_from_file(module):
    try:
        with open(module.params['configuration_data_path'], 'r') as f:
            file_content = json.load(f)
    except Exception as e:
        module.fail_json(msg='[read_policy_configuration_from_file] Error reading configuration data file (' + str(e) + ')')

    return file_content


def read_policy_pointcut_from_file(module):
    try:
        with open(module.params['pointcut_data_path'], 'r') as f:
            file_content = json.load(f)
    except Exception as e:
        module.fail_json(msg='[read_policy_pointcut_from_file] Error reading pointcut data file (' + str(e) + ')')

    return file_content


def need_to_update_configuration(module, policy_configuration, policy_pointcut, policy_rule_of_application):
    return_value = True
    # I leave this validation for future functionality changes, but today it is not necessary to check it
    default_rule = {
        "environmentId": module.params['environment_id'],
        "organizationId": module.params['organization_id'],
        "range": {
            "from": "4.1.1"
        }
    }
    configuration_content = read_policy_configuration_from_file(module)
    if (module.params.get('pointcut_data_path') is not None):
        pointcut_content = read_policy_pointcut_from_file(module)
    else:
        pointcut_content = None
    if ((default_rule == policy_rule_of_application)
            and (policy_configuration == configuration_content)
            and (policy_pointcut == pointcut_content)):
        return_value = False

    return return_value


def get_context(module):
    return_value = dict(
        do_nothing=False,
        policy_id=None,
        policy_asset_version=None,
        policy_enabled=False
    )
    policy_configuration = None
    list_applied_policies = get_applied_policies(module)
    # check if the API is already managed
    if (list_applied_policies is not None):
        for item in list_applied_policies:
            if (item['assetId'] == module.params['name']):
                return_value['policy_id'] = str(item['id'])
                return_value['policy_asset_version'] = item['assetVersion']
                return_value['policy_enabled'] = (item['disabled'] is False)
                policy_configuration = item['configurationData']
                policy_pointcut = item['pointcutData']
                policy_rule_of_application = item['ruleOfApplication']

    if (module.params['state'] == "present"):
        if (return_value['policy_id'] is not None):
            if (need_to_update_configuration(module, policy_configuration, policy_pointcut, policy_rule_of_application) is False):
                return_value['do_nothing'] = True
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['policy_id'] is None)

    return return_value


def remove_automated_policy(module, context):
    return_value = dict(
        policy_id=None,
        message=None
    )
    my_url = get_apim_automated_policies_url(module) + '/' + context['policy_id']
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}
    execute_http_call('[remove_automated_policy]', module, my_url, 'DELETE', headers, None)
    context['policy_id'] = None
    return_value['message'] = 'Automated policy removed'

    return return_value


def apply_edit_automated_policy(module, context):
    return_value = dict(
        policy_id=None,
        message=None
    )
    # first validate if it exists and if it is the desired version,
    # if not just remove it
    if (context['policy_id'] is not None and context['policy_asset_version'] != module.params['version']):
        remove_automated_policy(module, context)
        # set the context status for formality
        context['policy_id'] = None
        context['policy_asset_version'] = None
        context['policy_enabled'] = False
    # at this point we will apply either edit an existing policy
    # in both cases we need the options
    # read configuration data
    config_content = read_policy_configuration_from_file(module)
    # read poincut data
    if (module.params.get('pointcut_data_path') is not None):
        pointcut_content = read_policy_pointcut_from_file(module)
    else:
        pointcut_content = None
    # finally define other required variables
    policyId = context['policy_id']
    # create headers and payload
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {
        "configurationData": config_content,
        "id": policyId,
        "pointcutData": pointcut_content,
        "ruleOfApplication": {
            "environmentId": module.params['environment_id'],
            "organizationId": module.params['organization_id'],
            "range": {
                "from": "4.1.1"
            }
        },
        "groupId": module.params['group_id'],
        "assetId": module.params['name'],
        "assetVersion": module.params['version']
    }
    my_url = get_apim_automated_policies_url(module)
    if (policyId is not None):
        # if automated policy is already applied, then just update it
        my_url += '/' + policyId
        output = json.load(execute_http_call('[apply_edit_automated_policy]', module, my_url, 'PATCH', headers, payload))
        return_value['message'] = 'Automated policy updated'
    else:
        # apply a new automated policy
        output = json.load(execute_http_call('[apply_edit_automated_policy]', module, my_url, 'POST', headers, payload))
        return_value['message'] = 'Automated policy created'

    return_value['policy_id'] = output.get('id')

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=['present', 'absent']),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization_id=dict(type='str', required=True),
        environment_id=dict(type='str', required=False, default='Sandbox'),
        group_id=dict(type='str', required=False),
        version=dict(type='str', required=True),
        configuration_data_path=dict(type='str', required=False),
        pointcut_data_path=dict(type='str', required=False)
    )

    result = dict(
        changed=False,
        msg='No action taken',
        id=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # First check parameters
    if (module.params.get('group_id') is None) or (module.params.get('group_id') == ''):
        # MuleSoft default Organization ID for policies
        module.params['group_id'] = '68ef9520-24e9-4cf2-b2f5-620025690913'

    if (module.params['state'] == 'present'):
        if (module.params['environment_id'] is None):
            module.fail_json(msg="'environemt_id' parameter must be specified for 'present' state")
        if (module.params['version'] is None):
            module.fail_json(msg="'version' parameter must be specified for 'present' state")
        if (module.params['configuration_data_path'] is None):
            module.fail_json(msg="'configuration_data_path' parameter must be specified for 'present' state")
    # exit if I need to do nothing
    context = get_context(module)
    result['id'] = context['policy_id']
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # Parameters set & validation

    # check mode
    if module.check_mode:
        module.exit_json(**result)

    # Finally, execute some stuff
    if (module.params['state'] == 'present'):
        op_result = apply_edit_automated_policy(module, context)
    elif (module.params['state'] == 'absent'):
        op_result = remove_automated_policy(module, context)

    result['msg'] = op_result['message']
    result['id'] = op_result['policy_id']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
