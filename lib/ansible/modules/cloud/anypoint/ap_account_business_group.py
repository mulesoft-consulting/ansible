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
    parent_id:
        description:
            - The org id of the parent (if empty then master org is default)
    create_suborgs:
        description:
            - Enable creating subOrgs
        type: bool
        required: false
        default: false
    create_environments:
        description:
            - Enable creating environments
        type: bool
        required: false
        default: false
    global_deployment:
        description:
            - Enable global deployments
        type: bool
        required: false
        default: false
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
id:
    description: Created business group id
    type: str
    returned: success
client_id:
    description: Created business group clientId
    type: str
    returned: success
client_secret:
    description: Created business group clientSecret
    type: str
    returned: success
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_account_common
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.urls import open_url


def business_group_needs_update(module, bg):
    return_value = False
    if ((bg.get('entitlements').get('createSubOrgs') != module.params['create_suborgs'])
            or (bg.get('entitlements').get('createEnvironments') != module.params['create_environments'])
            or (bg.get('entitlements').get('globalDeployment') != module.params['global_deployment'])
            or (bg.get('entitlements').get('vCoresProduction').get('assigned') != module.params['vcores_production'])
            or (bg.get('entitlements').get('vCoresSandbox').get('assigned') != module.params['vcores_sandbox'])
            or (bg.get('entitlements').get('vCoresDesign').get('assigned') != module.params['vcores_design'])
            or (bg.get('entitlements').get('staticIps').get('assigned') != module.params['static_ips'])
            or (bg.get('entitlements').get('vpcs').get('assigned') != module.params['vpcs'])
            or (bg.get('entitlements').get('loadBalancer').get('assigned') != module.params['load_balancer'])
            or (bg.get('entitlements').get('vpns').get('assigned') != module.params['vpns'])):
        return_value = True

    return return_value


def get_context(module):
    return_value = dict(
        parent_id=None,
        parent_org_exists=False,
        target_id=None,
        target_client_id=None,
        target_client_secret=None,
        do_nothing=False,
        needs_update=False
    )
    org_list = ap_account_common.get_organizations_list(module)
    # first I need to identify the master org
    master_org = next(filter(lambda x: x['isMaster'] == True, org_list), None)
    if (master_org is None):
        module.fail_json(msg='[get_context] Error getting information about the master organization')
    # then, set the master org if no parent_id is present
    return_value['parent_id'] = module.params['parent_id']
    if (return_value['parent_id'] is None):
        return_value['parent_id'] = master_org['id']

    # now I need to iterate on the org list to get the right one
    for org in org_list:
        if (org['id'] == return_value['parent_id']):
            return_value['parent_org_exists'] = True
        if (org['parentId'] == return_value['parent_id'] and org['name'] == module.params['name']):
            return_value['target_id'] = org['id']
            return_value['target_client_id'] = org['clientId']
            break
    # If I didn't find it, maybe it is the master org
    if (return_value['target_id'] is None):
        if (master_org['name'] == module.params['name']):
            # target org is the master org
            return_value['parent_id'] = master_org['parentId']
            return_value['target_id'] = master_org['id']
            return_value['target_client_id'] = master_org['clientId']
            # this is a dummy assignation, there is no parent org for the master org
            return_value['parent_org_exists'] = True

    # If I found it, then gather additional info
    if (return_value['target_id'] is not None):
        return_value['target_client_secret'] = ap_account_common.get_business_group_client_secret(module, return_value['target_id'], return_value['target_client_id'])
        org_details = ap_account_common.get_organization(module, return_value['target_id'])
        return_value['needs_update'] = business_group_needs_update(module, org_details)

    # finally check if need to do anything
    if (module.params['state'] == 'present'):
        return_value['do_nothing'] = (return_value['target_id'] is not None and return_value['needs_update'] is False)
    elif (module.params['state'] == 'absent'):
        return_value['do_nothing'] = (return_value['target_id'] is None)

    return return_value


def get_user_id(module):
    return_value = ap_account_common.get_user_profile(module)
    return_value = return_value.get('id')

    return return_value


def create_business_group(module, context):
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
        "parentOrganizationId": context['parent_id'],
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

    resp_json = ap_common.execute_http_call('[create_business_group]', module, my_url, 'POST', headers, payload)

    return_value['bg_id'] = resp_json["id"]
    return_value['bg_client_id'] = resp_json["clientId"]
    return_value['bg_client_secret'] = ap_account_common.get_business_group_client_secret(module, resp_json["id"], resp_json["clientId"])

    return return_value


def update_business_group(module, context):
    return_value = dict(
        bg_id=None,
        bg_client_id=None,
        bg_client_secret=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + context['target_id']
    my_url = server_name + api_endpoint
    user_id = get_user_id(module)

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    payload = {
        "name": module.params['name'],
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

    ap_common.execute_http_call('[update_business_group]', module, my_url, 'PUT', headers, payload)

    return_value['bg_id'] = context['target_id']
    return_value['bg_client_id'] = context['target_client_id']
    return_value['bg_client_secret'] = context['target_client_secret']

    return return_value


def delete_business_group(module, context):
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/organizations/' + context['target_id']
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }
    ap_common.execute_http_call('[delete_business_group]', module, my_url, 'DELETE', headers, None)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        bearer=dict(type='str', required=True),
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        parent_id=dict(type='str', required=False),
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
        id=None,
        client_id=None,
        client_secret=None
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    if (module.params['parent_id'] == ''):
        module.params['parent_id'] = None
    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    context = get_context(module)
    result['id'] = context['target_id']
    result['client_id'] = context['target_client_id']
    result['client_secret'] = context['target_client_secret']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    if (context['parent_org_exists'] is False):
        module.fail_json(msg="parent org not found")

    if (module.params['state'] == 'present'):
        if (context['needs_update'] is False):
            output = create_business_group(module, context)
            result['changed'] = True
            result['id'] = output['bg_id']
            result['client_id'] = output['bg_client_id']
            result['client_secret'] = output['bg_client_secret']
            result['msg'] = 'Business Group created'
        else:
            output = update_business_group(module, context)
            result['changed'] = True
            result['msg'] = 'Business Group updated'
    elif (module.params['state'] == 'absent'):
        delete_business_group(module, context)
        result['changed'] = True
        result['id'] = None
        result['client_id'] = None
        result['client_secret'] = None
        result['msg'] = 'Business group deleted'

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
