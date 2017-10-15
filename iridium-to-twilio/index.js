'use strict';

let https = require('https');

console.log('Loading function');

const TWILIO_SID = process.env.TWILIO_ACCOUNT_SID;
const TWILIO_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const TWILIO_PHONE = process.env.TWILIO_PHONE_NUMBER;

exports.handler = (event, context, callback) => {
    console.log("Received message!", event, context);

    let p = urlDecode(event.body);
    let imei = p.imei;
    let data = p.data;
    
    let parsedData = hex2a(data);
    let [num, ...content] = parsedData.split(':');
    content = content.join(':');
    
    let post_params = {
        "To": num,
        "From": TWILIO_PHONE, 
        "Body": content
    };
    let post_data = urlEncode(post_params);
    
    const auth = `${TWILIO_SID}:${TWILIO_TOKEN}`;
    const auth_b64 = a2b64(auth);
    console.log("From", post_params.From, post_data);
    
    // TWILIO_URL = `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_SID}/Messages.json`
    let req = https.request({
        host: "api.twilio.com",
        port: 443,
        path: `/2010-04-01/Accounts/${TWILIO_SID}/Messages.json`,
        method: 'POST',
        headers: {
            'Authorization': `Basic ${auth_b64}`,
            'Content-Type': "application/x-www-form-urlencoded",
            'Content-Length': post_data.length
        }
    }, res => {
        var body = '';
        res.on('data', function(chunk)  {
            body += chunk;
        });

        res.on('end', function() {
            // context.done(body);
            callback(null, {
                statusCode: '200',
                body: 'ok',
                headers: {
                    'Content-Type': 'text/plain',
                },
            });
        });

        res.on('error', function(e) {
            // context.fail('error:' + e.message);
            callback(null, {
                statusCode: '500',
                body: 'not ok'+e.message,
                headers: {
                    'Content-Type': 'text/plain',
                },
            });
        });
    });
    req.write(post_data);
    req.end();
};


function urlEncode(obj) {
    return Object.keys(obj).map(k => `${k}=${encodeURIComponent(obj[k])}`).join("&");
}

function urlDecode(body) {
    var out = {};
    body.split('&').map(prop => prop.split('=')).forEach(([k, v]) => out[k] = decodeURIComponent(v));
    return out;
}

function hex2a(hex) {
    return new Buffer(hex, 'hex').toString();
}

function a2hex(a) {
    return new Buffer(a, 'ascii').toString('hex');
}

function a2b64(a) {
    return new Buffer(a, 'ascii').toString('base64');
}
