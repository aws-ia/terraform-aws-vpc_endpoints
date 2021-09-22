#!/usr/bin/env python3

import json
import boto3


def get_endpoint_services(session=boto3):
    ec2 = session.client('ec2', region_name='us-east-1')
    service_details = ec2.describe_vpc_endpoint_services()['ServiceDetails']
    svc_map = {"Interface": {}, "Gateway": {}}
    for svc in service_details:
        if svc['Owner'] != "amazon":
            print(f"skipping non-amazon endpoint {svc['ServiceName']}")
            continue
        if svc['AcceptanceRequired']:
            print(f"skipping endpoint that requires acceptance {svc['ServiceName']}")
            continue
        if svc['ManagesVpcEndpoints']:
            print(f"skipping endpoint that manages vpc endpoints {svc['ServiceName']}")
            continue
        svc_type = svc["ServiceType"][0]["ServiceType"]
        svc_name = svc["ServiceName"]
        if svc_name.startswith("aws.sagemaker."):
            svc_name = f'sagemaker.{svc_name.split(".")[-1]}'
        elif svc_name.startswith("com.amazonaws."):
            if svc_name.split('.')[2] != 'us-east-1':
                svc_name = '.'.join(svc_name.split('.')[2:])
            else:
                svc_name = '.'.join(svc_name.split('.')[3:])
        else:
            print(f"skipping endpoint that has unexpected name format {svc['ServiceName']}")
            continue
        svc_name = svc_name.replace(".", "_")
        if len(svc['BaseEndpointDnsNames']) > 1:
            for i in range(len(svc['BaseEndpointDnsNames']) - 1):
                if svc['BaseEndpointDnsNames'][i].startswith(svc['ServiceId']):
                    svc['BaseEndpointDnsNames'].pop(i)
        if len(svc['BaseEndpointDnsNames']) > 1:
            print(f"skipping endpoint that has unexpected additional dns name {svc['ServiceName']} "
                  f"{svc['BaseEndpointDnsNames']}")
            continue
        private_dns_name = svc['PrivateDnsName'].replace("us-east-1", "<REGION>") if svc.get('PrivateDnsName') else None
        svc_map[svc_type][svc_name] = {
            'ServiceName': svc["ServiceName"].replace("us-east-1", "<REGION>"),
            # AZ's need more work, need to build a map of all supported az id's(not names) across all partitions
            # "AvailabilityZones": svc.get("AvailabilityZones"),
            'BaseEndpointDnsName': svc['BaseEndpointDnsNames'][0].replace("us-east-1", "<REGION>"),
            'VpcEndpointPolicySupported': svc['VpcEndpointPolicySupported'],
            'PrivateDnsName': private_dns_name
        }
    return svc_map


def generate_tf_json(endpoints):
    with open('./templates/locals.tf.json') as fp:
        tf_locals_template = json.load(fp)
    with open('./templates/main.tf.json') as fp:
        tf_resources_template = json.load(fp)
    with open('./templates/outputs.tf.json') as fp:
        tf_outputs_template = json.load(fp)
    with open('./templates/variables.tf.json') as fp:
        tf_variables_template = json.load(fp)
    tf_endpoints = tf_resources_template['resource']['aws_vpc_endpoint']
    tf_variables = tf_variables_template['variable']
    allowed_policy_keys = {"Interface": set(), "Gateway": set()}
    available_endpoints = {"Interface": set(), "Gateway": set()}
    for endpoint_type, eps in endpoints.items():
        for name, ep in eps.items():
            resource_name = f"{name}_{endpoint_type.lower()}"
            tf_endpoints[resource_name] = {
                "count": '${contains(var.enabled_%s_endpoints, "%s") ? 1 : 0}' % (endpoint_type.lower(), name),
                "service_name": regional_string(ep["ServiceName"]),
                "vpc_endpoint_type": endpoint_type,
                "tags": "${var.tags}",
                "auto_accept": True,
                "vpc_id": "${var.vpc_id}"
            }
            if endpoint_type == 'Gateway':
                tf_endpoints[resource_name]['route_table_ids'] = '${length(var.route_table_ids) > 0 ? var.route_table_ids : null}'
            elif endpoint_type == 'Interface':
                tf_endpoints[resource_name]['security_group_ids'] = '${var.security_group_ids}'
                tf_endpoints[resource_name]['subnet_ids'] = '${length(var.subnet_ids) > 0 ? var.subnet_ids : null}'
            if ep["VpcEndpointPolicySupported"]:
                tf_endpoints[resource_name]['policy'] = '${try(jsonencode(var.%s_endpoint_policies.%s), null)}' % (endpoint_type.lower(), name)
                allowed_policy_keys[endpoint_type].add(name)
            available_endpoints[endpoint_type].add(name)
    for ep_type in ["Interface", "Gateway"]:
        tf_var_name = f"enabled_{ep_type.lower()}_endpoints"
        tf_policy_var = f"{ep_type.lower()}_endpoint_policies"
        regex = regex_builder(available_endpoints[ep_type])
        tf_variables[tf_var_name]["description"] = tf_variables[tf_var_name]["description"] + "\n\nAvailable endpoints:\n* " + "\n* ".join(sorted(available_endpoints[ep_type]))
        tf_variables[tf_var_name]["validation"] = {
            "condition": """${var.%s == [] ? true : can([for s in var.%s : regex("%s", s)])}""" % (tf_var_name, tf_var_name, regex),
            "error_message": f"Endpoint names can only contain one or more of the following {sorted(available_endpoints[ep_type])}."
        }
        tf_variables[tf_policy_var]["validation"] = {
            "condition": """${[for k, v in var.%s: k] == [] ? true : can([for s in [for k, v in var.%s: k] : regex("%s", s)])}""" % (
            tf_policy_var, tf_policy_var, regex),
            "error_message": f"Endpoint names can only contain one or more of the following {sorted(available_endpoints[ep_type])}."
        }
    with open('./main.tf.json', "w") as fp:
        json.dump(tf_resources_template, fp, indent=2)
    with open('./variables.tf.json', "w") as fp:
        json.dump(tf_variables_template, fp, indent=2)


def regex_builder(available_endpoints):
    regex = ""
    for endpoint in available_endpoints:
        regex = regex + f"||${endpoint}^"
    return regex


def regional_string(string):
    return '${replace("%s", "<REGION>", data.aws_region.current.name)}' % string


if __name__ == '__main__':
    endpoints = get_endpoint_services()
    generate_tf_json(endpoints)