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
module: ap_account_business_group

short_description: Manage business groups on Anypoint Platform Account

version_added: "2.8"

description:
    - "This module supports management of business group at Master org level on Anypoint Platform Accounts"

options:
    name:
        description:
            - Business Group name
        required: true
    state:
        description:
            - Assert the state of the BG. Use Use C(present) to create a BG and C(absent) to delete it.
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
    create_suborgs:
        description:
            - Enable creating subOrgs
        required: false
        default: false
        choices: [ "true", "false" ]
    create_environments:
        description:
            - Enable creating environments
        required: false
        default: false
        choices: [ "true", "false" ]
    global_deployment:
        description:
            - Enable global deployments
        required: false
        default: false
        choices: [ "true", "false" ]
    vcores_production:
        description:
            - Number of Production vCores assigner
        required: false
        default: 0
    vcores_sandbox:
        description:
            - Number of Sandbox vCores assigned
        required: false
        default: 0
    vcores_design:
        description:
            - Number of Design vCores assigned
        required: false
        default: 0
    static_ips:
        description:
            - Number of Static IPs assigned
        required: false
        default: 0
    vpcs:
        description:
            - Number of VPCs assigned
        required: false
        default: 0
    load_balancer:
        description:
            - Number of Load Balancers assigned
        required: false
        default: 0
    vpns:
        description:
            - Number of VPNs assigned
        required: false
        default: 0

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating an empty business group
- name: create a business group
  ap_account_business_group:
    name: 'My Demos'
    state: "present"
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'

# Example of creating business group with 0.2 Sandbox vCores that allows creatin suborgs
- name: create a gusiness group
  ap_account_business_group:
    name: 'My Demos'
    state: "present"
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    create_suborgs: true
    vcores_sandbox: 0.2

# Example of deleting a business group
- name: delete a gusiness group
  ap_account_business_group:
    name: 'My Demos'
    state: "absent"
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
'''

RETURN = '''
bg_id:
    description: Created business group id
    type: string
    returned: success
bg_client_id:
    description: Created business group clientId
    type: string
    returned: success
bg_client_secret:
    description: Created business group clientSecret
    type: string
    returned: success
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.urls import open_url


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def get_business_group_client_secret(module, bg_id, bg_client_id):
    return_value = None
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + bg_id + '/clients/' + bg_client_id
    my_url = server_name + api_endpoint
    user_id = get_user_id(module)

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.exit_json(msg=str(e))

    resp_json = json.loads(resp.read())

    return resp_json['client_secret']


def do_no_action(module):
    return_value = dict(
        master_id=None,
        target_id=None,
        target_client_id=None,
        target_client_secret=None
    )
    bearer_arg = '--bearer="' + module.params['bearer'] + '"'
    host_arg = '--host="' + module.params['host'] + '"'
    args = 'account business-group list --output json'
    cmd = get_anypointcli_path(module) + ' ' + bearer_arg + ' ' + host_arg + ' ' + args
    result = module.run_command(cmd)

    if result[0] != 0:
        return_value['msg'] = result[1]
        module.exit_json(msg=result[1])

    resp_json = json.loads(result[1])

    for item in resp_json:
        if (item['Type'] == 'Master'):
            return_value['master_id'] = item['Id']
            break

    # check if business group exists
    # I call the API instead of using anypoint-cli output because I found that after deleting
    # a BG, the list operation is still showing it
    # https://www.mulesoft.org/jira/browse/APC-23
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + return_value['master_id'] + '/hierarchy'
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.exit_json(msg=str(e))

    resp_json = json.loads(resp.read())
    for item in resp_json['subOrganizations']:
        if (item['name'] == module.params['name']):
            return_value['target_id'] = item['id']
            return_value['target_client_id'] = item['clientId']
            return_value['target_client_secret'] = get_business_group_client_secret(module, item['id'], item['clientId'])

            break

    return return_value


def get_user_id(module):
    return_value = ''
    bearer_arg = '--bearer="' + module.params['bearer'] + '"'
    host_arg = '--host="' + module.params['host'] + '"'
    args = 'account user describe --output json'
    cmd = get_anypointcli_path(module) + ' ' + bearer_arg + ' ' + host_arg + ' ' + args

    result = module.run_command(cmd)
    if result[0] != 0:
        module.exit_json(msg=result[1])

    # check if the environment exists
    if len(result[1]) > 2:
        resp_json = json.loads(result[1])
        return_value = resp_json['Id']
    else:
        module.exit_json(msg='Unknown error')

    return return_value


def create_business_group(module, master_id):
    return_value = dict(
        bg_id=None,
        bg_client_id=None,
        bg_client_secret=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations'
    my_url = server_name + api_endpoint
    user_id = get_user_id(module)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    payload = {
        "name": module.params['name'],
        "parentOrganizationId": master_id,
        "ownerId": user_id,
        "entitlements": {
            "createSubOrgs": module.params['create_suborgs'],
            "createEnvironments": module.params['create_environments'],
            "globalDeployment": module.params['global_deployment'],
            "vCoresProduction": {
                "assigned": module.params['vcores_production']
            },
            "vCoresSandbox": {
                "assigned": module.params['vcores_sandbox']
            },
            "vCoresDesign": {
                "assigned": module.params['vcores_design']
            },
            "staticIps": {
                "assigned": module.params['static_ips']
            },
            "vpcs": {
                "assigned": module.params['vpcs']
            },
            "loadBalancer": {
                "assigned": module.params['load_balancer']
            },
            "vpns": {
                "assigned": module.params['vpns']
            }
        }
    }

    try:
        resp = open_url(my_url, method="POST", headers=headers, data=json.dumps(payload))
    except Exception as e:
        module.exit_json(msg=str(e))

    resp_json = json.loads(resp.read())
    return_value['bg_id'] = resp_json["id"]
    return_value['bg_client_id'] = resp_json["clientId"]
    return_value['bg_client_secret'] = get_business_group_client_secret(module, resp_json["id"], resp_json["clientId"])

    return return_value


def delete_business_group(module, target_id):
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + target_id
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    try:
        resp = open_url(my_url, method="DELETE", headers=headers)
    except Exception as e:
        module.fail_json(msg=str(e))


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        bearer=dict(type='str', required=True),
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        create_suborgs=dict(type='bool', required=False, default=False),
        create_environments=dict(type='bool', required=False, default=False),
        global_deployment=dict(type='bool', required=False, default=False),
        vcores_production=dict(type='float', required=False, default=0),
        vcores_sandbox=dict(type='float', required=False, default=0),
        vcores_design=dict(type='float', required=False, default=0),
        static_ips=dict(type='float', required=False, default=0),
        vpcs=dict(type='float', required=False, default=0),
        load_balancer=dict(type='float', required=False, default=0),
        vpns=dict(type='float', required=False, default=0)
    )

    result = dict(
        changed=False,
        msg='No action taken',
        bg_id=None,
        bg_client_id=None,
        bg_client_secret=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    context = do_no_action(module)

    if (module.params['state'] == 'present'):
        if (context['target_id'] is not None):
            # do nothing
            result['bg_id'] = context['target_id']
            result['bg_client_id'] = context['target_client_id']
            result['bg_client_secret'] = context['target_client_secret']
            module.exit_json(**result)
        else:
            output = create_business_group(module, context['master_id'])

            result['changed'] = True
            result['bg_id'] = output['bg_id']
            result['bg_client_id'] = output['bg_client_id']
            result['bg_client_secret'] = output['bg_client_secret']
            result['msg'] = 'Business Group created'

    elif (module.params['state'] == 'absent'):
        if context['target_id'] is None:
            # do nothing
            module.exit_json(**result)
        delete_business_group(module, context['target_id'])
        result['changed'] = True
        result['bg_id'] = None
        result['bg_client_id'] = None
        result['bg_client_secret'] = None
        result['msg'] = 'Business group deleted'

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
