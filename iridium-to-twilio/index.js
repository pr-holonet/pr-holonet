'use strict';

const https = require('https');
const querystring = require('querystring');
const twilio = require('twilio');

const TWILIO_SID = process.env.TWILIO_ACCOUNT_SID;
const TWILIO_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const TWILIO_PHONE = process.env.TWILIO_PHONE_NUMBER;


exports.handler = (ev, context, callback) => {
    if (ev.headers['User-Agent'].startsWith('TwilioProxy')) {
        handleFromTwilio(ev, context, callback);
    }
    else {
        handleFromIridium(ev, context, callback);
    }
};

function handleFromTwilio(ev, context, callback) {
    if (!validateTwilioSignature(ev)) {
        callback(null, {
            statusCode: '403',
        });
        return;
    }



    callback(null, {
        statusCode: '200',
        body: 'ok',
        headers: {
            'Content-Type': 'text/plain',
        },
    });
}

function validateTwilioSignature(ev) {
    const headers = ev.headers;
    const host = headers.Host;
    const reqPath = ev.requestContext.path;
    const twilioSignature = headers['X-Twilio-Signature'];
    const url = `https://${host}${reqPath}`;
    const params = querystring.decode(ev.body);
    const result = twilio.validateRequest(TWILIO_TOKEN, twilioSignature, url,
                                          params);
    if (!result) {
        console.log("Twilio signature validation failed!", url, params,
                    twilioSignature)
    }
    return result;
}

function handleFromIridium(ev, context, callback) {
    const p = querystring.decode(ev.body);
    const data = p.data;
    const parsedData = hex2a(data);
    const [num, content] = splitWithTail(parsedData, ':', 1);

    const client = new twilio.Twilio(TWILIO_SID, TWILIO_TOKEN);
    client.messages.create({
        from: TWILIO_PHONE,
        to: num,
        body: content,
    }, function(err, result) {
        if (err) {
            console.log('Error response from Twilio: ', err)
            callback(null, {
                statusCode: '500',
                body: 'not ok',
                headers: {
                    'Content-Type': 'text/plain',
                },
            });
        }
        else {
            callback(null, {
                statusCode: '200',
                body: 'ok',
                headers: {
                    'Content-Type': 'text/plain',
                },
            });
        }
    });
}


function hex2a(hex) {
    return new Buffer(hex, 'hex').toString();
}

function splitWithTail(str, delim, count) {
  const parts = str.split(delim);
  const tail = parts.slice(count).join(delim);
  let result = parts.slice(0, count);
  result.push(tail);
  return result;
}
