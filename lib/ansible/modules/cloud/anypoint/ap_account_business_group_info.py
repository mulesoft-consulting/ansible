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
module: ap_account_business_group_info

short_description: GAther information abount a business groups on Anypoint Platform Account

version_added: "2.8"

description:
    - "This module supports management of business group at Master org level on Anypoint Platform Accounts"

options:
    name:
        description:
            - Business Group name
        required: true
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform instance
        required: false
        default: anypoint.mulesoft.com
    parent_id:
        description:
            - The org id of the parent
            - if empty then either master org is default or master org is the target

author:
    - Gonzalo Camino (@gonzalo-camino)
'''

EXAMPLES = '''
# Example of gathering info from a  business group at master level
- name: get info abount a business group
  ap_account_business_group_info:
    name: 'My Demos'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'

# Example of gathering info from a  business group with parent different than master
- name: get info abount a business group
  ap_account_business_group_info:
    name: 'My Demos'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    parent_id: '2fd8fa2f-b980-453e-956a-d93c947e3421'
'''

RETURN = '''
id:
    description: Business group id
    type: str
    returned: success
name:
    description: Business group name
    type: str
    returned: success
client_id:
    description: Business group clientId
    type: str
    returned: success
client_secret:
    description: Business group clientSecret
    type: str
    returned: success
is_master:
    description: If business group is master org or not
    type: str
    returned: success
is_federated:
    description: id business group id federated or not
    type: str
    returned: success
idprovider_id:
    description: Business group provider id
    type: str
    returned: success
owner_id:
    description: Business group owner id
    type: str
    returned: success
created_at:
    description: Business group creation date
    type: str
    returned: success
parent:
    description:
        - info about parent org
        - it is empty if business group is the master org
    type: dict
    contains:
        id:
            description: Parent Org ID
            type: str
            returned: success
        name:
            description: Parent Org name
            type: str
            returned: success
environments:
    description: List with business group environments
    type: list
    returned: success
    contains:
        id:
            description: Environment id
            type: str
            returned: success
        name:
            description: Environment name
            type: str
            returned: success
        type:
            description: Environment type
            type: str
            returned: success
        is_production:
            description: Environment is production type or not
            type: str
            returned: success
        client_id:
            description: Environment clientId
            type: str
            returned: success
entitlements:
    description: List with business group entitlements
    returned: success
    type: dict
    contains:
        create_suborgs:
            description: Create subOrgs enabled
            type: bool
        create_environments:
            description: Create environments enabled
            type: bool
        global_deployment:
            description: Global deployments enabled
            type: bool
        vcores_production:
            description: available and allocated vcores for production environment
            type: dict
            contains:
                assigned:
                    description: Assigned vcores for production environment
                    type: float
                used:
                    description: Used vcores for production environment
                    type: float
        vcores_sandbox:
            description: available and allocated vcores for sandbox environment
            type: dict
            contains:
                assigned:
                    description: Assigned vcores for sandbox environment
                    type: float
                used:
                    description: Used vcores for sandbox environment
                    type: float
        vcores_design:
            description: available and allocated vcores for design environment
            type: dict
            contains:
                assigned:
                    description: Assigned vcores for design environment
                    type: float
                used:
                    description: Used vcores for design environment
                    type: float
        load_balancer:
            description: available and allocated load balancers
            type: dict
            contains:
                assigned:
                    description: Assigned load balancers
                    type: float
                used:
                    description: Used load balancers
                    type: float
        vpns:
            description: available and allocated vpns
            type: dict
            contains:
                assigned:
                    description: Assigned vpns
                    type: float
                used:
                    description: USed vpns
                    type: float

'''

import json
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_account_common
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode
from ansible.module_utils.urls import open_url


def get_business_group_usage(module, bg_id):
    return_value = dict(
        production=None,
        sandbox=None,
        design=None,
        load_balancers=None,
        vpns=None
    )
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/cs/organizations/' + bg_id + '/usage'
    my_url = server_name + api_endpoint

    headers = {
        'Accept': 'application/json',
        'Authorization': 'bearer ' + module.params['bearer']
    }

    resp_json = ap_common.execute_http_call('[get_business_group_usage]', module, my_url, 'GET', headers, None)
    return_value['production'] = resp_json['productionVCoresConsumed']
    return_value['sandbox'] = resp_json['sandboxVCoresConsumed']
    return_value['design'] = resp_json['designVCoresConsumed']
    return_value['load_balancers'] = resp_json['loadBalancersConsumed']
    return_value['vpns'] = resp_json['vpnsConsumed']

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        bearer=dict(type='str', required=True),
        name=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        parent_id=dict(type='str', required=False)
    )

    result = dict(
        id=None,
        name=None,
        client_id=None,
        client_secret=None,
        is_master=None,
        is_federated=None,
        idprovider_id=None,
        owner_id=None,
        created_at=None,
        parent=None,
        environments=None,
        entitlements=None
    )
    # parent
    parent = dict(
        id=None,
        name=None
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

    org_list = ap_account_common.get_organizations_list(module)
    # first I need to identify the master org
    master_org = next(filter(lambda x: x['isMaster'] is True, org_list), None)
    if (master_org is None):
        module.fail_json(msg='[run_module] Error getting information about the master organization')
    # then, set the master org if no parent_id is present
    tmp_parent_id = module.params['parent_id']
    if (tmp_parent_id is None):
        tmp_parent_id = master_org['id']

    # now I need to iterate on the org list to get the right one
    for org in org_list:
        if (tmp_parent_id == org['parentId'] and module.params['name'] == org['name']):
            parent['id'] = org['parentId']
            parent['name'] = org['parentName']
            result['id'] = org['id']
            result['name'] = org['name']
            result['client_id'] = org['clientId']
            result['is_master'] = org['isMaster']
            result['is_federated'] = org['isFederated']
            result['idprovider_id'] = org['idprovider_id']
            result['owner_id'] = org['ownerId']
            result['created_at'] = org['createdAt']
            result['parent'] = parent
            break

    # now I need to process the exceptions
    if (result['id'] is None):
        if (master_org['name'] != module.params['name']):
            # target org not found
            module.exit_json(**result)
        else:
            # target org is the master org
            parent['id'] = master_org['parentId']
            parent['name'] = master_org['parentName']
            result['id'] = master_org['id']
            result['name'] = master_org['name']
            result['client_id'] = master_org['clientId']
            result['is_master'] = master_org['isMaster']
            result['is_federated'] = master_org['isFederated']
            result['idprovider_id'] = master_org['idprovider_id']
            result['owner_id'] = master_org['ownerId']
            result['created_at'] = master_org['createdAt']
            result['parent'] = parent

    # map the rest of the org info
    result['client_secret'] = ap_account_common.get_business_group_client_secret(module, result['id'], result['client_id'])
    child = ap_account_common.get_organization(module, result['id'])
    # environments
    result['environments'] = []
    for environment in child['environments']:
        env = dict(
            id=None,
            name=None,
            is_production=None,
            client_id=None,
            type=None
        )
        env['id'] = environment['id']
        env['name'] = environment['name']
        env['is_production'] = environment['isProduction']
        env['client_id'] = environment['clientId']
        env['type'] = environment['type']
        result['environments'].append(env)
    # entitlements
    entitl = dict(
        create_suborgs=None,
        create_environments=None,
        global_deployment=None,
        vcores_production=dict(
            assigned=None,
            used=None
        ),
        vcores_sandbox=dict(
            assigned=None,
            used=None
        ),
        vcores_design=dict(
            assigned=None,
            used=None
        ),
        load_balancer=dict(
            assigned=None,
            used=None
        ),
        vpns=dict(
            assigned=None,
            used=None
        ),

    )
    bg_usage = get_business_group_usage(module, result['id'])
    entitl['create_suborgs'] = child['entitlements']['createSubOrgs']
    entitl['create_environments'] = child['entitlements']['createEnvironments']
    entitl['global_deployment'] = child['entitlements']['globalDeployment']
    entitl['vcores_production']['assigned'] = child['entitlements']['vCoresProduction']['assigned']
    entitl['vcores_production']['used'] = bg_usage['production']
    entitl['vcores_sandbox']['assigned'] = child['entitlements']['vCoresSandbox']['assigned']
    entitl['vcores_sandbox']['used'] = bg_usage['sandbox']
    entitl['vcores_design']['assigned'] = child['entitlements']['vCoresDesign']['assigned']
    entitl['vcores_design']['used'] = bg_usage['design']
    entitl['load_balancer']['assigned'] = child['entitlements']['loadBalancer']['assigned']
    entitl['load_balancer']['used'] = bg_usage['load_balancers']
    entitl['vpns']['assigned'] = child['entitlements']['vpns']['assigned']
    entitl['vpns']['used'] = bg_usage['vpns']
    result['entitlements'] = entitl

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
