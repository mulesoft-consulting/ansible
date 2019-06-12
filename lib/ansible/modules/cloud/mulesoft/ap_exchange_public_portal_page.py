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
module: ap_exchange_public_portal_page

short_description: Manage a page on Anypoint Platform Exchange Public portal

version_added: "2.8"

description:
    - "Create or delete a page on Anypoint Platform Exchange Public portal"

options:
    name:
        description:
            - Page name (also used as path)
        required: true
    state:
        description:
            - Assert the state of the page. Use C(present) to create an page and C(absent) to delete it.
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
    md_path:
        description:
            - Path to the file with page content in markdown
        required: false

author:
    - Gonzalo Camino (@gonzalo-camino)
'''

EXAMPLES = '''
# Create a page with no content
- name: create page on exchange public portal with no content
  ap_exchange_public_portal_page:
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    name: 'My Demos Page'
    state: 'present'

# Create a page with content
- name: create page on exchange public portal with content
  ap_exchange_public_portal_page:
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    name: 'My Demos Page'
    state: 'present'
    md_path: '/tmp/mypage.md'

# Delete a page
- name: delete page on exchange public portal with no content
  ap_exchange_public_portal_page:
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    name: 'My Demos Page'
    state: 'absent'
'''

RETURN = '''
msg:
    description: The output message that the module generates
    type: string
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.parse import urlencode, quote
from ansible.module_utils.urls import open_url


def get_domain(module):
    server_name = 'https://' + module.params['host']
    api_endpoint = '/accounts/api/profile'
    my_url = server_name + api_endpoint
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.fail_json(msg='[get_domain] ' + str(e))

    resp_json = json.loads(resp.read())
    return resp_json["organization"]["domain"]


def get_exchange_portal_base_url(module):
    return 'https://' + module.params['host'] + '/exchange/api/v1/organizations/' + get_domain(module) + '/portal'


def get_portal_pages(module):
    exchange_portal_base_url = get_exchange_portal_base_url(module)
    my_url = exchange_portal_base_url

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.fail_json(msg='[get_portal_pages] ' + str(e))

    return json.loads(resp.read())['pages']


def do_no_action(module):
    return_value = dict(
        value=False,
        needs_creation=False
    )
    page_exists = False
    pages = get_portal_pages(module)

    for item in pages:
        if (item['name'] == module.params['name']):
            page_exists = True
            break

    if (module.params['state'] == 'present'):
        if (page_exists is False):
            return_value['value'] = False
            return_value['needs_creation'] = True
        else:
            if (module.params['md_path'] is None):
                # create page empty requested
                return_value['value'] = True
                return_value['needs_creation'] = False
            else:
                # update the page content requested
                return_value['value'] = False
                return_value['needs_creation'] = False
    elif (module.params['state'] == 'absent'):
        return_value['value'] = not page_exists
        needs_creation = False

    return return_value


def get_portal_draft_content(module, portal_url):
    my_url = portal_url + '/draft'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.fail_json(msg='[get_portal_draft_content] ' + str(e))
    resp_json = json.loads(resp.read())

    return resp_json


def publish_portal(module, portal_url):
    my_url = portal_url + '/draft'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = get_portal_draft_content(module, portal_url)
    # update content
    try:
        resp = open_url(my_url, method="PUT", headers=headers, data=json.dumps(payload))
    except Exception as e:
        module.fail_json(msg='[publish_portal] ' + str(e))
    # publish
    my_url = portal_url
    try:
        resp = open_url(my_url, method="PATCH", headers=headers, data='')
    except Exception as e:
        module.fail_json(msg='[publish_portal] ' + str(e))


def update_page_content_only(module, exchange_portal_base_url):
    server_name = get_exchange_portal_base_url(module)
    api_endpoint = '/draft/pages/' + quote(module.params['name'])
    my_url = server_name + api_endpoint

    headers = {
        'Content-Type': 'text/markdown',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    # load content
    try:
        f = open(module.params['md_path'], 'r')
        payload = f.read()
        f.close()
        resp = open_url(my_url, method="PUT", headers=headers, data=payload)
    except Exception as e:
        module.fail_json(msg='[update_page_content_only] ' + str(e))

    # publish portal draft
    publish_portal(module, server_name)


def create_page(module):
    exchange_portal_base_url = get_exchange_portal_base_url(module)
    api_endpoint = '/draft/pages'
    my_url = exchange_portal_base_url + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    payload = {
        'pagePath': module.params['name']
    }
    # create page
    try:
        resp = open_url(my_url, method="POST", headers=headers, data=json.dumps(payload))
    except Exception as e:
        module.fail_json(msg='[create_page] ' + str(e))

    # set page content if any
    if (module.params['md_path'] is not None):
        update_page_content_only(module, exchange_portal_base_url)

    # publish portal draft
    publish_portal(module, exchange_portal_base_url)


def update_page(module):
    exchange_portal_base_url = get_exchange_portal_base_url(module)
    update_page_content_only(module, exchange_portal_base_url)

    # publish portal draft
    publish_portal(module, exchange_portal_base_url)


def delete_page(module):
    exchange_portal_base_url = get_exchange_portal_base_url(module)
    api_endpoint = '/draft/pages/' + quote(module.params['name'])
    my_url = exchange_portal_base_url + api_endpoint

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    try:
        resp = open_url(my_url, method="DELETE", headers=headers)
    except Exception as e:
        module.fail_json(msg='[delete_page] ' + str(e))

    # publish portal draft
    publish_portal(module, exchange_portal_base_url)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        md_path=dict(type='str', required=False, default=None)
    )

    result = dict(
        changed=False,
        msg=''
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

    # exit if I need to do nothing, so check if asset exists in exchange
    context = do_no_action(module)
    if (context['value'] is True):
        module.exit_json(**result)

    # Main Module Logic
    if (module.params['state'] == 'present'):
        if (context['needs_creation'] is True):
            # create page and set content if any
            create_page(module)
        elif (module.params['md_path'] is not None):
            # only set content
            update_page(module)
            result['msg'] = 'page created'

    elif (module.params['state'] == 'absent'):
        delete_page(module)
        result['msg'] = 'page deleted'

    result['changed'] = True
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
