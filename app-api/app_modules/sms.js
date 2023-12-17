var signer = require('./signer');
var https = require("https");
var url = require('url');
var querystring = require('querystring');
var realUrl = 'https://smsapi.cn-north-4.myhuaweicloud.com:443/sms/batchSendSms/v1';
var appKey = 'lt7Klp06gISA42uy1ClA5uVI020v';
var appSecret = 'prDEfZRWYlupUsBdp9e0ZRQnPIUd';
var sender = '8823120828568';
var templateId = '6b268b26ac7542fe9906165e95412aa4';
var signature = "华为云短信测试";

function sendVerificationCode(receiver, code) {
  var statusCallBack = '';

  var templateParas = `["${code}"]`;

  var urlobj = url.parse(realUrl);

  var sig = new signer.Signer();
  sig.Key = appKey;
  sig.Secret = appSecret;

  var r = new signer.HttpRequest("POST", realUrl);
  r.headers = { "Content-Type": "application/x-www-form-urlencoded" };
  r.body = buildRequestBody(sender, receiver, templateId, templateParas, statusCallBack, signature);

  var opt = sig.Sign(r);
  opt.hostname = urlobj.hostname
  opt.port = urlobj.port
  console.log(opt)

  var req = https.request(opt, function (res) {
    console.log(res.statusCode);
    console.log('headers:', JSON.stringify(res.headers));
    res.on("data", function (chunk) {
      console.log(chunk.toString())
    })
  });

  req.on("error", function (err) {
    console.log(err.message)
  });
  req.write(r.body);
  req.end();


  function buildRequestBody(sender, receiver, templateId, templateParas, statusCallBack, signature) {
    if (null !== signature && signature.length > 0) {
      return querystring.stringify({
        'from': sender,
        'to': receiver,
        'templateId': templateId,
        'templateParas': templateParas,
        'statusCallback': statusCallBack,
        'signature': signature
      });
    }

    return querystring.stringify({
      'from': sender,
      'to': receiver,
      'templateId': templateId,
      'templateParas': templateParas,
      'statusCallback': statusCallBack
    });
  }
}

module.exports = { sendVerificationCode };