#!/usr/bin/env python3

import json
import boto3

AWS_REGION = 'us-east-1'
TF_TEMPLATE_PATH = 'templates/{}.tf.json.template'
TF_OUTPUT_PATH = '../{}.tf.json'
KNOWN_PREFIXES = ["aws.", "com.amazonaws."]
VALIDATION_CONDITION_STRING = """${var.%s == [] ? true : can([for s in var.%s : regex("%s", s)])}"""
VALIDATION_CONDITION_STRING_POLICY = (
    """${[for k, v in var.%s: k] == [] ? true : can([for s in [for k, v in var.%s: k] : regex("%s", s)])}"""
)
VALIDATION_ERROR_MESSAGE = "Endpoint names can only contain one or more of the following {}."


def generate_tf_json(endpoints):
    tf_resources_template = get_template("main")
    tf_locals_template = get_template("locals")
    tf_variables_template = get_template("variables")
    tf_endpoints = tf_resources_template['resource']['aws_vpc_endpoint']
    tf_locals = tf_locals_template['locals']
    tf_variables = tf_variables_template['variable']
    allowed_policy_keys = {"Interface": set(), "Gateway": set()}
    available_endpoints = {"Interface": set(), "Gateway": set()}
    for endpoint_type, eps in endpoints.items():
        for name, ep in eps.items():
            parse_endpoint(name, endpoint_type, tf_endpoints, tf_locals, ep, available_endpoints, allowed_policy_keys)
        create_tf_variables(endpoint_type, available_endpoints, tf_variables)
    write_tf('main', tf_resources_template)
    write_tf('locals', tf_locals_template)
    write_tf('variables', tf_variables_template)


def get_available_endpoints(session=boto3):
    ec2 = session.client('ec2', region_name=AWS_REGION)
    service_details = ec2.describe_vpc_endpoint_services()['ServiceDetails']
    svc_map = {"Interface": {}, "Gateway": {}}
    for svc in service_details:
        if not endpoint_is_valid:
            continue
        svc_type = svc["ServiceType"][0]["ServiceType"]
        svc_name = get_short_name(svc["ServiceName"])
        private_dns_name = svc['PrivateDnsName'].replace(AWS_REGION, "<REGION>") if svc.get('PrivateDnsName') else None
        svc_map[svc_type][svc_name] = {
            'ServiceName': svc["ServiceName"].replace(AWS_REGION, "<REGION>"),
            # AZ's need more work, need to build a map of all supported az id's(not names) across all partitions
            # "AvailabilityZones": svc.get("AvailabilityZones"),
            'BaseEndpointDnsName': svc['BaseEndpointDnsNames'][0].replace(AWS_REGION, "<REGION>"),
            'VpcEndpointPolicySupported': svc['VpcEndpointPolicySupported'],
            'PrivateDnsName': private_dns_name
        }
    return svc_map


def endpoint_is_valid(svc):
    if svc['Owner'] != "amazon":
        print(f"skipping non-amazon endpoint {svc['ServiceName']}")
        return False
    if svc['AcceptanceRequired']:
        print(f"skipping endpoint that requires acceptance {svc['ServiceName']}")
        return False
    if svc['ManagesVpcEndpoints']:
        print(f"skipping endpoint that manages vpc endpoints {svc['ServiceName']}")
        return False
    if not svc["ServiceName"].startswith("com.amazonaws.") and not svc["ServiceName"].startswith("aws.sagemaker."):
        print(f"skipping endpoint that has unexpected name format {svc['ServiceName']}")
        return False
    trim_base_endpoint_names(svc)
    if len(svc['BaseEndpointDnsNames']) > 1:
        print(f"skipping endpoint that has unexpected additional dns name {svc['ServiceName']} "
              f"{svc['BaseEndpointDnsNames']}")
        return False
    return True


def get_short_name(endpoint_name):
    for prefix in KNOWN_PREFIXES:
        if endpoint_name.startswith(prefix):
            endpoint_name = endpoint_name[len(prefix):]
            if endpoint_name.startswith(f"{AWS_REGION}."):
                endpoint_name = endpoint_name[len(f"{AWS_REGION}."):]
            return endpoint_name.replace(".", "_")
    raise ValueError(f"{endpoint_name} does not start with a prefix in the list of known prefixes: {KNOWN_PREFIXES}")


def trim_base_endpoint_names(endpoint):
    if len(endpoint['BaseEndpointDnsNames']) > 1:
        for i in range(len(endpoint['BaseEndpointDnsNames']) - 1):
            if endpoint['BaseEndpointDnsNames'][i].startswith(endpoint['ServiceId']):
                endpoint['BaseEndpointDnsNames'].pop(i)


def get_template(name):
    with open(TF_TEMPLATE_PATH.format(name)) as fp:
        template = json.load(fp)
    return template


def write_tf(name, file_data):
    with open(TF_OUTPUT_PATH.format(name), "w") as fp:
        json.dump(file_data, fp, indent=2)


def parse_endpoint(name, endpoint_type, tf_endpoints, tf_locals, ep, available_endpoints, allowed_policy_keys):
    resource_name = f"{name.replace('-', '_')}_{endpoint_type.lower()}"
    tf_endpoints[resource_name] = {
        "count": '${contains(var.enabled_%s_endpoints, "%s") ? 1 : 0}' % (endpoint_type.lower(), name),
        "service_name": regional_string(ep["ServiceName"]),
        "vpc_endpoint_type": endpoint_type,
        "tags": "${var.tags}",
        "auto_accept": True,
        "vpc_id": "${var.vpc_id}"
    }
    if endpoint_type == 'Gateway':
        tf_endpoints[resource_name][
            'route_table_ids'] = '${length(var.route_table_ids) > 0 ? var.route_table_ids : null}'
    elif endpoint_type == 'Interface':
        tf_endpoints[resource_name]['security_group_ids'] = '${var.security_group_ids}'
        tf_endpoints[resource_name]['subnet_ids'] = '${length(var.subnet_ids) > 0 ? var.subnet_ids : null}'
    if ep["VpcEndpointPolicySupported"]:
        tf_endpoints[resource_name]['policy'] = '${try(jsonencode(var.%s_endpoint_policies.%s), null)}' % (
        endpoint_type.lower(), name)
        allowed_policy_keys[endpoint_type].add(name)
    tf_locals[f"{endpoint_type.lower()}_output_dict"][name] = (
        "${length(resource.aws_vpc_endpoint.%s) == 1 ? resource.aws_vpc_endpoint.%s[0] : null}"
    ) % (resource_name, resource_name)
    available_endpoints[endpoint_type].add(name)


def create_tf_variables(endpoint_type, available_endpoints, tf_variables):
    endpoints = sorted(available_endpoints[endpoint_type].copy())
    tf_var_name = f"enabled_{endpoint_type.lower()}_endpoints"
    tf_policy_var = f"{endpoint_type.lower()}_endpoint_policies"
    regex = regex_builder(endpoints)
    tf_var = tf_variables[tf_var_name]
    tf_var["description"] = tf_var["description"] + "Available endpoints:" + ", ".join(endpoints)
    tf_var["validation"] = {
        "condition": VALIDATION_CONDITION_STRING % (tf_var_name, tf_var_name, regex),
        "error_message": VALIDATION_ERROR_MESSAGE.format(endpoints)
    }
    tf_variables[tf_policy_var]["validation"] = {
        "condition": VALIDATION_CONDITION_STRING_POLICY % (tf_policy_var, tf_policy_var, regex),
        "error_message": VALIDATION_ERROR_MESSAGE.format(endpoints)
    }


def regex_builder(available_endpoints):
    regex = ""
    for endpoint in available_endpoints:
        regex = regex + f"||${endpoint}^"
    return regex


def regional_string(string):
    return '${replace("%s", "<REGION>", data.aws_region.current.name)}' % string


if __name__ == '__main__':
    generate_tf_json(get_available_endpoints())
