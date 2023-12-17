const fetch = require('node-fetch');
const app = require('fastify')()
const mysql = require('mysql2/promise');
const argon2 = require('argon2');
const jwt = require('jsonwebtoken');
const fs = require("fs");

const accountAPI = require("./app_modules/account");
const essayAPI = require("./app_modules/essay");

const API_PREFIX = "/api";

const keyPriv = fs.readFileSync('key-priv.pem');
const keyPub = fs.readFileSync('key-pub.pem');

const commonFns = {
  async signJwt(payload) {
    return jwt.sign(payload, keyPriv, { algorithm: "RS256", expiresIn: "720h" });
  },
  async verifyJwt(token) {
    try {
      return jwt.verify(token, keyPub, { algorithms: ["RS256"] });
    }
    catch (e) {
      return false;
    }
  },
  async issueJwtFromRow(userRow) {
    return commonFns.signJwt({
      uid: userRow.id,
      quota: userRow.quota,
      tier: userRow.tier,
      verified: userRow.verified,
    });
  },
};

let dbConn;

async function init() {
  dbConn = mysql.createPool({
    host: 'localhost',
    user: 'language',
    password: 'USPSFedEx1',
    database: 'language',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0,
    enableKeepAlive: true,
    keepAliveInitialDelay: 0
  });

  accountAPI.registerAccountAPI(app, dbConn, commonFns, API_PREFIX);
  essayAPI.registerEssayAPI(app, dbConn, commonFns, API_PREFIX);

  // RESTRICTING USAGE
  app.addHook('onRequest', (request, reply, done) => {
    const headerValue = request.headers.parrot;
  
    if (headerValue && headerValue == "5ea4bff4-8b1b-453f") {
      done();
    } else {
      reply.code(400).send({ error: 'Invalid request' });
    }
  });

  app.listen({ port: 8082 }, (err) => {
    if (err) {
      console.log(err)
      process.exit(1)
    }
  })
}
init();