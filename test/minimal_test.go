package test

import (
	"context"
	"fmt"
	"github.com/aws/aws-sdk-go-v2/service/ec2/types"
	"github.com/aws/aws-sdk-go/aws"
	"strings"

	"testing"

	"github.com/aws/aws-sdk-go-v2/service/ec2"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var testPath = "examples/minimal"

var testCasesMinimal = []testCase{
	{name: "validate endpoints created are as expected", function: validateEndpoints},
	{name: "validates endpoint is associated with the expected security group", function: validateSgAssociated},
}

func validateEndpoints(t *testing.T, tfOpts *terraform.Options) {
	s3Arn := terraform.Output(t, tfOpts, "s3_arn")
	s3Dns := terraform.Output(t, tfOpts, "s3_private_dns")
	stsArn := terraform.Output(t, tfOpts, "sts_arn")
	stsDns := terraform.Output(t, tfOpts, "sts_private_dns")
	require.NotNil(t, s3Arn, "s3 endpoint should be created")
	require.NotNil(t, stsArn, "sts endpoint should be created")
	assert.True(t, strings.HasPrefix(stsArn, "arn:"), "should output a valid arn")
	assert.True(t, stsDns == "true", "private dns should be enabled")
	assert.True(t, strings.HasPrefix(s3Arn, "arn:"), "should output a valid arn")
	assert.True(t, s3Dns == "false", "private dns cannot be enabled for s3 interface endpoint")
}

func validateSgAssociated(t *testing.T, tfOpts *terraform.Options) {
	sgIds := terraform.OutputList(t, tfOpts, "security_group_ids")
	require.NotNil(t, sgIds, "a security group should be created when one is not provided")
	require.Equal(t, 1, len(sgIds), "there should be one security group created")
	assert.True(t, strings.HasPrefix(sgIds[0], "sg-"), "should output a valid security group id")
}

func createVpc(t *testing.T, region string, profile string) string {
	client := getEc2Client(profile, region)
	createVpcResponse, err := client.CreateVpc(context.TODO(), &ec2.CreateVpcInput{
		CidrBlock: aws.String("10.0.0.0/16"),
	})
	require.Nil(t, err)
	_, err = client.ModifyVpcAttribute(context.TODO(), &ec2.ModifyVpcAttributeInput{
		VpcId: createVpcResponse.Vpc.VpcId,
		EnableDnsHostnames: &types.AttributeBooleanValue{
			Value: aws.Bool(true),
		},
	})
	require.Nil(t, err)
	_, err = client.ModifyVpcAttribute(context.TODO(), &ec2.ModifyVpcAttributeInput{
		VpcId: createVpcResponse.Vpc.VpcId,
		EnableDnsSupport: &types.AttributeBooleanValue{
			Value: aws.Bool(true),
		},
	})
	require.Nil(t, err)
	return *createVpcResponse.Vpc.VpcId
}

func cleanTestVpc(t *testing.T, vpcId string, region string, profile string) {
	fmt.Println("Removing VPC begun...")
	client := getEc2Client(profile, region)
	_, err := client.DeleteVpc(context.TODO(), &ec2.DeleteVpcInput{
		VpcId: aws.String(vpcId),
	})
	require.Nil(t, err)
	fmt.Println("Removing VPC complete.")
}

func TestMinimal(t *testing.T) {
	t.Parallel()
	//doTest(t, "us-west-2", "default")
	// TODO: dry
	uw2vpcId := createVpc(t, "us-west-2", "default")
	t.Cleanup(func() {
		cleanTestVpc(t, uw2vpcId, "us-west-2", "default")
	})
	ue2vpcId := createVpc(t, "us-east-2", "default")
	t.Cleanup(func() {
		cleanTestVpc(t, ue2vpcId, "us-east-2", "default")
	})
	var testVarsMinimal = []map[string]interface{}{
		{"region": "us-west-2", "profile": "default", "vpc_id": uw2vpcId},
		{"region": "us-east-2", "profile": "default", "vpc_id": ue2vpcId},
	}
	RunTests(t, testVarsMinimal, testCasesMinimal, testPath)
}
