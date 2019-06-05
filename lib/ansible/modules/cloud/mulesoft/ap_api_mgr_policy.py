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
module: ap_api_mgr_policy

short_description: Manage policies over managed APIs on API Manager

version_added: "2.8"

description:
    - "This module supports basic operations for applying/enabling/disabling and removing policies over managed APIs on Anypoint Platform API Manager"

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
        choices: [ "present", "enabled", "disabled", absent" ]
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
    environment:
        description:
            - Environment on the Business Group to work on
        required: false
        default: Sandbox
    policy_version:
        description:
            - Mule 4 policy version. Required only for C(present) state
        required: false
        default: '1.0.0'
    api_instance_id:
        description:
            - The managed API instance ID
        required: true
    options:
        description:
            - the policy configuration. Required for C(present) state
        suboptions:
            group_id:
                description:
                    - Mule 4 policy group ID. If no value is provided, this value defaults to MuleSoft group ID.
                required: false
            config_path:
                description:
                    - Pass the file path with the configuration data as a JSON string. Required only for C(present) state
                required: false
            pointcut_path:
                description:
                    - Pass the file path with the pointcut data as JSON strings.
                required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of applying a policy on an existing Amanaged API
- name: Apply policy API
  ap_api_mgr_policy:
    name: 'client-id-enforcement'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization: 'My Demos'
    environment: 'Sandbox'
    api_instance_id: '15722837'
    policy_version: '1.1.8'


# Example of enabling a policy on an existing managed API
- name: Enable an applied policy on managed API
  ap_api_mgr_policy:
    name: 'client-id-enforcement'
    state: 'enabled'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization: 'My Demos'
    environment: 'Sandbox'
    api_instance_id: '15722837'

# Example of disabling a policy on an existing managed API
- name: Disable an applied policy on managed API
  ap_api_mgr_policy:
    name: 'client-id-enforcement'
    state: 'disabled'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization: 'My Demos'
    environment: 'Sandbox'
    api_instance_id: '15722837'

# Example of a removing a policy on an existing managed API
- name: Remove a policy from a managed API
  ap_api_mgr_api:
    name: 'client-id-enforcement'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization: 'My Demos'
    environment: 'Sandbox'
    api_instance_id: '15722837'
'''

RETURN = '''
policy_id:
    description: Policy ID
    type: string
    returned: success
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
import re
from ansible.module_utils.basic import AnsibleModule


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def check_if_update_needed(module, cmd_base, api_instance_id):
    return_value = False
    not_found_regex = '^Error: API with ID "[0-9]{5,}" not found in environment ID' \
                      '"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"'
    cmd_final = cmd_base
    cmd_final += ' describe ' + api_instance_id + ' --output json'

    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    resp_json = json.loads(result[1])
    # validate field by field
    if (resp_json.get('Instance Label') is None and module.params['instance_label'] is not None):
        return_value = True
    elif (resp_json.get('Deprecated') == 'Y'):
        # this doesn't work, actually anypoint-cli is always returning 'N'
        # https://www.mulesoft.org/jira/browse/APC-22
        return_value = True
    elif (resp_json.get('Implementation URI') is None and module.params['uri'] is not None):
        return True
    elif (resp_json.get('Proxy URI') is None and module.params['with_proxy'] is True):
        return True

    return return_value


def execute_anypoint_cli(module, cmd):
    result = module.run_command(cmd)
    if result[0] != 0:
        module.fail_json(msg=result[1])

    return result[1]


def get_applied_policies(module, cmd_base):
    return_value = json.loads('[]')
    cmd_final = cmd_base
    cmd_final += ' list'
    cmd_final += ' ' + str(module.params['api_instance_id'])
    cmd_final += ' --output json'

    output = execute_anypoint_cli(module, cmd_final)
    if (len(output) > 2):
        return_value = json.loads(output)

    return return_value


def do_no_action(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        policy_id=None,
        policy_asset_version=None,
        policy_enabled=False
    )

    list_applied_policies = get_applied_policies(module, cmd_base)
    # check if the API is already managed
    if (list_applied_policies is not None):
        for item in list_applied_policies:
            if (item['Asset ID'] == module.params['name']):
                return_value['policy_id'] = str(item['ID'])
                return_value['policy_asset_version'] = item['Asset Version']
                return_value['policy_enabled'] = (item['Status'] == 'Enabled')

    if (module.params['state'] == "enabled"):
        if (return_value['policy_id'] is None):
            module.fail_json(msg='enabled state requires an existing policy applied')
        return_value['do_nothing'] = (return_value['policy_enabled'] is True)
    elif (module.params['state'] == "disabled"):
        if (return_value['policy_id'] is None):
            module.fail_json(msg='disabled state requires an existing policy applied')
        return_value['do_nothing'] = (return_value['policy_enabled'] is False)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['policy_id'] is None)

    return return_value


def apply_edit_policy_on_api(module, cmd_base, context):
    return_value = ''
    # first validate if it exists and if it is the desired version,
    # if not just remove it
    if (context['policy_id'] is not None and context['policy_asset_version'] != module.params['policy_version']):
        tmp = remove_policy_from_api(module, cmd_base, context)
        # set the context status for formality
        context['policy_id'] = None
        context['policy_asset_version'] = None
        context['policy_enabled'] = False
    # at this point we will apply either edit an existing policy
    # in both cases we need the options
    try:
        f = open(module.params['options']['config_path'], 'r')
        config_content = f.read().replace('\n', '')
        f.close()
        if (module.params['options'].get('pointcut_path') is not None):
            f = open(module.params['options']['pointcut_path'], 'r')
            pointcut_content = f.read().replace('\n', '')
            f.close()
        else:
            pointcut_content = None
    except Exception as e:
        module.fail_json(msg=str(e))
    options_arg = " --config '" + config_content + "'"
    # if poincut is null then it applies to all methods!
    if (pointcut_content is not None):
        options_arg += " --pointcut '" + pointcut_content + "'"

    if (context['policy_id'] is not None):
        # if policy is already applied, then just update it
        cmd_final = cmd_base
        cmd_final += ' edit'
        cmd_final += options_arg
        cmd_final += ' "' + module.params['api_instance_id'] + '"'
        cmd_final += ' "' + context['policy_id'] + '"'
        return_value = execute_anypoint_cli(module, cmd_final)
    else:
        # apply a new policy
        if (module.params['options'].get('group_id') is not None):
            options_arg += ' --groupId "' + module.params['group_id'] + '"'
        options_arg += ' --policyVersion "' + module.params['policy_version'] + '"'
        cmd_final = cmd_base
        cmd_final += ' apply'
        cmd_final += options_arg
        cmd_final += ' "' + module.params['api_instance_id'] + '"'
        cmd_final += ' "' + module.params['name'] + '"'
        return_value = execute_anypoint_cli(module, cmd_final).replace('\n', '')
        tmp = return_value.replace('Policy applied. New policy ID: ', '').replace('\"', '')
        context['policy_id'] = tmp

    return return_value


def enable_policy_on_api(module, cmd_base, context):
    return_value = 'N/A'
    cmd_final = cmd_base
    cmd_final += ' enable'
    cmd_final += ' "' + module.params['api_instance_id'] + '"'
    cmd_final += ' "' + context['policy_id'] + '"'
    return_value = execute_anypoint_cli(module, cmd_final)

    return return_value.replace('\n', '')


def disable_policy_on_api(module, cmd_base, context):
    return_value = 'N/A'
    cmd_final = cmd_base
    cmd_final += ' disable'
    cmd_final += ' "' + module.params['api_instance_id'] + '"'
    cmd_final += ' "' + context['policy_id'] + '"'
    return_value = execute_anypoint_cli(module, cmd_final)

    return return_value.replace('\n', '')


def remove_policy_from_api(module, cmd_base, context):
    return_value = 'N/A'
    cmd_final = cmd_base
    cmd_final += ' remove'
    cmd_final += ' "' + module.params['api_instance_id'] + '"'
    cmd_final += ' "' + context['policy_id'] + '"'
    return_value = execute_anypoint_cli(module, cmd_final)

    return return_value.replace('\n', '')


def run_module():
    # define specs
    options_spec = dict(
        group_id=dict(type='str', required=False),
        config_path=dict(type='str', required=False),
        pointcut_path=dict(type='str', required=False)
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=['present', 'enabled', 'disabled', 'absent']),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        environment=dict(type='str', required=False, default='Sandbox'),
        policy_version=dict(type='str', required=False, default='1.0.0'),
        api_instance_id=dict(type='str', required=True),
        options=dict(type='dict', options=options_spec)
    )

    result = dict(
        changed=False,
        msg='No action taken',
        policy_id=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' --environment="' + module.params['environment'] + '"'
    cmd += ' api-mgr policy'
    cmd_base = cmd

    # exit if I need to do nothing
    context = do_no_action(module, cmd_base)
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # Parameters set & validation

    # check mode
    if module.check_mode:
        module.exit_json(**result)

    # Finally, execute some stuff
    if (module.params['state'] == 'present'):
        op_result = apply_edit_policy_on_api(module, cmd_base, context)
    elif (module.params['state'] == 'enabled'):
        op_result = enable_policy_on_api(module, cmd_base, context)
    elif (module.params['state'] == 'disabled'):
        op_result = disable_policy_on_api(module, cmd_base, context)
    elif (module.params['state'] == 'absent'):
        op_result = remove_policy_from_api(module, cmd_base, context)

    result['msg'] = op_result
    result['changed'] = True
    result['policy_id'] = context['policy_id']

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
