package test

import (
	"context"
	"fmt"
	"github.com/aws/aws-sdk-go/aws"
	"strings"

	//"fmt"
	//"github.com/aws/aws-sdk-go-v2/service/ec2/types"
	"testing"

	//"github.com/aws/aws-sdk-go-v2/aws"
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
	require.NotNil(t, s3Arn, "s3 endponit should be created")
	assert.True(t, strings.HasPrefix(s3Arn, "arn:"), "should output a valid arn")
}

func validateSgAssociated(t *testing.T, tfOpts *terraform.Options) {
	subnetIds := terraform.OutputList(t, tfOpts, "security_group_ids")
	require.NotNil(t, subnetIds, "a subnet should be created when one is not provided")
	require.Equal(t, 1, len(subnetIds), "there should be one security group created")
	assert.True(t, strings.HasPrefix(subnetIds[0], "sg-"), "should output a valid security group id")
}

func createVpc(t *testing.T, region string, profile string) string {
	client := getEc2Client(profile, region)
	createVpcResponse, err := client.CreateVpc(context.TODO(), &ec2.CreateVpcInput{
		CidrBlock: aws.String("10.0.0.0/16"),
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
