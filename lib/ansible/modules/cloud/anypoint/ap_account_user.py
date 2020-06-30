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
module: ap_account_user

short_description: Create or Delete User on Account

version_added: "2.8"

description:
    - "This module supports basic operations to create or delete users on Anypoint Platform Accounts"

options:
    name:
        description:
            - User name
        required: true
    state:
        description:
            - Assert the state of the user. Use C(present) to create or enable a user, C(disabled) to disable a user or C(absent) to delete it.
        required: true
        choices: [ "present", "disabled", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    organization_id:
        description:
            - Anypoint Platform Organization Id to work on
        required: true
    first_name:
        description:
            - First name of the user
        required: true
    last_name:
        description:
            - Last name of the user
    email:
        description:
            - Email of the user
    password:
        description:
            - Password of the user

author:
    - Gonzalo Camino (@gonzalo-camino)

'''

EXAMPLES = '''
# Example of creating a User
- name: Create User
  ap_account_user:
    name: 'gcamino'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com'
    organization_id: '3cf447de-4c32-46b9-ab3d-e74ced87a0c2'
    first_name: 'Gonzalo'
    last_name: 'Camino'
    email: 'gonzalo.camino@mulesoft.com'
    password: 'toor'

# Example of deleting a User
- name: Delete a User
  ap_account_user:
    name: 'gcamino'
    state: 'absent'
    bearer: '3cf447de-4c32-46b9-ab3d-e74ced87a0c2'
    organization_id: 'My Demos'
'''

RETURN = '''
id:
    description: Id for the user
    type: str
    returned: always
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''


import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_account_common


def user_needs_update(module, user):
    return_value = False
    if ((module.params['first_name'] != user['firstName'])
            or (module.params['last_name'] != user['lastName'])
            or (module.params['email'] != user['email'])):
        return_value = True

    return return_value


def get_context(module):
    return_value = dict(
        do_nothing=False,
        id=None,
        enabled=False
    )
    needs_update = False
    resp_json = ap_account_common.get_users_list(module, module.params['organization_id'], False)
    for user in resp_json:
        if (user['username'] == module.params['name']):
            return_value['id'] = user['id']
            return_value['enabled'] = user['enabled']
            needs_update = user_needs_update(module, user)
            break
    # finally check if I need to do anything or not
    if (module.params['state'] == "absent"):
        return_value['do_nothing'] = (return_value['id'] is None)
    elif (module.params['state'] == "present"):
        if (return_value['id'] is None):
            return_value['do_nothing'] = False
        else:
            return_value['do_nothing'] = not ((needs_update is True) or (return_value['enabled'] is False))
    elif (module.params['state'] == "disabled"):
        return_value['do_nothing'] = not ((return_value['id'] is not None) and (return_value['enabled'] is True))
    return return_value


def create_user(module):
    return_value = dict(
        id=None,
        msg=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + module.params['organization_id'] + '/users'
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    payload = {
        "username": module.params['name'], 
        "firstName": module.params['first_name'], 
        "lastName": module.params['last_name'], 
        "email": module.params['email'], 
        "password": module.params['password']
    }
    resp_json = ap_common.execute_http_call('[create_user]', module, my_url, 'POST', headers, payload)
    return_value['id'] = resp_json['id']
    return_value['msg'] = 'user created'

    return return_value


def change_user_enablement(module, context, enabled):
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + module.params['organization_id'] + '/users'
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    payload = [{
        "id": context['id'], 
        "enabled": enabled
    }]
    ap_common.execute_http_call('[change_user_enablement]', module, my_url, 'PUT', headers, payload)


def update_user(module, context):
    return_value = dict(
        id=None,
        msg=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + module.params['organization_id'] + '/users/' + context['id']
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    payload = {
        "firstName": module.params['first_name'], 
        "lastName": module.params['last_name'], 
        "email": module.params['email']
    }
    ap_common.execute_http_call('[update_user]', module, my_url, 'PUT', headers, payload)
    if (context['enabled'] is False):
        change_user_enablement(module, context, True)
    return_value['id'] = context['id']
    return_value['msg'] = 'user updated'

    return return_value


def delete_user(module, context):
    return_value = dict(
        id=None,
        msg=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + module.params['organization_id'] + '/users/' + context['id']
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    ap_common.execute_http_call('[delete_user]', module, my_url, 'DELETE', headers, None)
    return_value['id'] = None
    return_value['msg'] = 'user deleted'

    return return_value


def disable_user(module, context):
    return_value = dict(
        id=None,
        msg=None
    )
    change_user_enablement(module, context, False)
    return_value['id'] = context['id']
    return_value['msg'] = 'user disabled'

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "disabled", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization_id=dict(type='str', required=True),
        first_name=dict(type='str', required=True),
        last_name=dict(type='str', required=True),
        email=dict(type='str', required=True),
        password=dict(type='str', required=True),
    )

    result = dict(
        changed=False,
        id=None,
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
    context = get_context(module)
    result['id'] = context['id']
    result['enabled'] = context['enabled']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    # Parameters set action
    if module.params['state'] == "present":
        if (context['id'] is None):
            output = create_user(module)
        else:
            output = update_user(module, context)
    elif module.params['state'] == "absent":
        output = delete_user(module, context)
    elif module.params['state'] == "disabled":
        output = disable_user(module, context)

    result['msg'] = output['msg']
    result['id'] = output['id']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
