# Iridium-to-Twilio bridge

This is a function that runs on AWS Lambda.  Whenever the Iridium service
receives a message from a user (via the Holonet device) it is passed to
the RockBLOCK service, which in turn notifies us with a webhook.  This
triggers the Lambda function here, which forwards it to Twilio for sending as
an SMS on the cell network.  The reverse path is also handled here, receiving
a webhook from Twilio and forwarding the message to RockBLOCK.

## Setup instructions

These instructions use the AWS CLI to create the Lambda function and
associated role, and jq to filter the AWS responses.

### Get the dependencies from NPM

```
# From pr-holonet/iridium-to-twilio
npm install --prefix=.
```

### Configure the AWS CLI

Create a file with your AWS credentials.  For example, `~/.aws-pr-holonet.cfg`:

```
[default]
region=us-east-1
aws_access_key_id=<Your key ID>
aws_secret_access_key=<Your access key>
```

Reference this with

```
export AWS_CONFIG_FILE=~/.aws-pr-holonet.cfg
```

### Configure imeiToNumber.json

The file `imeiToNumber.json` contains a mapping of RockBLOCK-registered
IMEIs to Twilio-registered phone numbers.

This is used for two things:

1. checking a message from RockBLOCK to validate that it is actually from one
of our devices (preventing spam);
2. routing messages from cellphone users (via Twilio) to the correct Holonet
device.

This should look something like below.  Every time you register a new
RockBLOCK, you need to add an entry to this file, and redeploy the AWS Lambda
stack.

```
{
    "292487138892290": "+13975658547"
}
```

### Create the stack

```
# From pr-holonet/iridium-to-twilio

region='us-east-1'
stack_name='iridium-to-twilio-stack'
bucket_name='pr-holonet-iridium-to-twilio'
rockblock_username='<Your RockBLOCK username>'
rockblock_password='<Your RockBLOCK password>'
twilio_account='<Your Twilio account ID>'
twilio_auth_token='<Your Twilio auth token>'
twilio_phone_no='+15556667777 <phone number registered with Twilio>'

# Delete the existing stack if necessary.  Usually you don't need to do this.
# aws cloudformation delete-stack --stack-name "$stack_name"

# Package the template and the code.  This copies the code to an S3 bucket.
aws cloudformation package \
    --template-file holonet-handler.yaml \
    --output-template-file holonet-handler.packaged.yaml \
    --s3-bucket "$bucket_name"

# Deploy the package.
aws cloudformation deploy \
    --capabilities CAPABILITY_NAMED_IAM \
    --template-file holonet-handler.packaged.yaml \
    --stack-name "$stack_name" \
    --parameter-overrides RockBlockUsername="$rockblock_username" \
                          RockBlockPassword="$rockblock_password" \
                          TwilioAuthToken="$twilio_auth_token" \
                          TwilioAccountSid="$twilio_account" \
                          TwilioPhoneNumber="$twilio_phone_no"

# Get REST API URL.
rest_api_id=$(
    aws apigateway get-rest-apis | \
        jq -r ".items[] | select (.name=\"$stack_name\") | .id")
handler_url="https://$rest_api_id.execute-api.$region.amazonaws.com/Prod/holonet-handler"
echo "Endpoint is $handler_url"
```

### Configure the handler URL with Twilio and RockBLOCK

The endpoint printed by the last command above goes into the Twilio console
under https://www.twilio.com/console > Phone numbers > your configured number >
A call comes in.  The settings should be "Webhook" and "HTTP Post".

It also goes into the RockBLOCK console under
https://rockblock.rock7.com/Operations > Delivery Groups > All devices >
Delivery Addresses.
