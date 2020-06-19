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
module: ap_account_environment

short_description: Create or Delete Environment on Account

version_added: "2.8"

description:
    - "This module supports basic operations for create or delete environments on Anypoint Platform Accounts"

options:
    name:
        description:
            - Environment name
        required: true
    state:
        description:
            - Assert the state of the environment. Use C(present) to create an environment and C(absent) to delete it.
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
    type:
        description:
            - Environment type
        choices: [ "design", "sandbox", "production" ]
        default: production
        required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating a Production Environment
- name: Create the Production Environment
  ap_account_environment:
    name: 'Production'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization: 'My Demos'

# Example of creating a Development Environment
- name: Create the Development Environment
  ap_account_environment:
    name: 'Development'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    type: 'sandbox'

# Example of creating a deleting an Environment
- name: Delete the Development Environment
  ap_account_environment:
    name: 'Development'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
'''

RETURN = '''
id:
    description: Id for the environment
    type: str
    returned: always
client_id:
    description: Client id for the environment
    type: str
    returned: always
client_secret:
    description: Client secret for the environment
    type: str
    returned: always
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_account_common


def get_environment(module, cmd_base):
    return_value = None
    error_message = 'Error: Environment not found'
    cmd_final = cmd_base
    cmd_final += ' describe'
    cmd_final += ' "' + module.params['name'] + '"'
    cmd_final += ' --output json'
    result = module.run_command(cmd_final)
    if (result[0] == 0):
        return_value = json.loads(result[1])
    elif (result[0] == 255 and result[1].replace('\n', '') == error_message):
        return_value = {}
    else:
        module.fail_json(msg=result[1])

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        id=None,
        client_id=None,
        client_secret=None,
        org_id=None
    )
    return_value['org_id'] = ap_account_common.get_organization_id(module, module.params['organization'])
    resp_json = get_environment(module, cmd_base)
    if (resp_json != {}):
        return_value['id'] = resp_json['ID']
        return_value['client_id'] = resp_json['Client ID']

    if (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['id'] is None)
    elif (module.params['state'] == "present"):
        if (return_value['id'] is None):
            return_value['do_nothing'] = False
        else:
            client_secret = ap_account_common.get_organization_client_secret(
                module,
                return_value['org_id'],
                return_value['client_id']
            )
            return_value['client_secret'] = client_secret
            return_value['do_nothing'] = True

    return return_value


def create_environment(module, context, cmd_base):
    return_value = dict(
        id=None,
        client_id=None,
        client_secret=None,
        msg=None
    )
    cmd_final = cmd_base
    cmd_final += ' create --type ' + module.params['type']
    cmd_final += ' "' + module.params['name'] + '"'
    resp = ap_common.execute_anypoint_cli('[create_environment]', module, cmd_final)

    resp_json = get_environment(module, cmd_base)
    return_value['id'] = resp_json['ID']
    return_value['client_id'] = resp_json['Client ID']
    client_secret = ap_account_common.get_organization_client_secret(module, context['org_id'], return_value['client_id'])
    return_value['client_secret'] = client_secret
    return_value['msg'] = 'environment created'

    return return_value


def delete_environment(module, cmd_base):
    return_value = dict(
        id=None,
        client_id=None,
        client_secret=None,
        msg=None
    )
    cmd_final = cmd_base
    cmd_final += ' delete'
    cmd_final += ' "' + module.params['name'] + '"'
    resp = ap_common.execute_anypoint_cli('[delete_environment]', module, cmd_final)
    return_value['msg'] = 'environment deleted'

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        type=dict(type='str', required=False, default="production", choices=["design", "sandbox", "production"])
    )

    result = dict(
        changed=False,
        id=None,
        client_id=None,
        client_secret=None,
        msg='No action taken'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (ap_common.get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    cmd = ap_common.get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' account environment'
    cmd_base = cmd

    # exit if I need to do nothing, so check if environment exists
    context = get_context(module, cmd_base)
    result['id'] = context['id']
    result['client_id'] = context['client_id']
    result['client_secret'] = context['client_secret']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # Parameters set action
    if module.params['state'] == "present":
        output = create_environment(module, context, cmd_base)
    elif module.params['state'] == "absent":
        output = delete_environment(module, cmd_base)

    result['msg'] = output['msg']
    result['id'] = output['id']
    result['client_id'] = output['client_id']
    result['client_secret'] = output['client_secret']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
