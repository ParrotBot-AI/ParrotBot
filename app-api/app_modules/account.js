const fetch = require('node-fetch');
const app = require('fastify')()
const mysql = require('mysql2/promise');
const argon2 = require('argon2');
const jwt = require('jsonwebtoken');
const fs = require("fs");

const { sendVerificationCode } = require("./sms");

async function registerAccountAPI(app, dbConn, commonFns, API_PREFIX) {
  app.get(`${API_PREFIX}/account/checkToken`, {
    async handler(request, reply) {
      if (!request.headers.authorization) {
        reply.send({ error: "token" });
        return;
      }

      const user = await commonFns.verifyJwt(request.headers.authorization);

      let [rows, fields] = await dbConn.execute(`SELECT quota FROM user WHERE id = ?`, [user.uid]);

      user.quota = rows[0].quota;

      if (user) {
        reply.send({ error: null, type: "token-check", data: user });
      }
      else {
        reply.send({ error: "token" });
      }
    },
  });
  
  app.post(`${API_PREFIX}/account/verify`, {
    schema: {
      body: {
        type: 'object',
        required: ["tel", "password", "otp"],
        properties: {
          tel: { type: 'string' },
          password: { type: 'string' },
          otp: { type: 'string' },
        },
      },
    },
    async handler (request, reply) {
      try {
        const [rows, fields] = await dbConn.execute(
          'SELECT * FROM `user` WHERE `id` = ?',
          [request.body.tel]
        );
  
        if (rows.length === 1) {
          if (rows[0].verified) {
            reply.send({ error: "error" });
          }
          else {
            // check OTP and expiry
            if (
              rows[0].otp === request.body.otp &&
              rows[0].otpExp.getTime() > (new Date()).getTime() &&
              await argon2.verify(rows[0].password, request.body.password)
            ) {
              await dbConn.execute(
                'UPDATE `user` SET `verified` = 1 WHERE `id` = ?',
                [request.body.tel]
              );
              rows[0].verified = 1;
              reply.send({
                error: null,
                type: "token-issue",
                data: {
                  token: await commonFns.issueJwtFromRow(rows[0]),
                },
              });
            }
            else {
              reply.send({ error: "user" });
            }
          }
        }
        else {
          reply.send({ error: "error" });
        }
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
  
  async function otpCreate(tel) {
    const otp = Math.floor(100000 + Math.random() * 900000);
    await dbConn.execute(
      'UPDATE `user` SET `otp` = ?, `otpExp` = ? WHERE `id` = ?',
      [otp.toString(), new Date(new Date().getTime() + 3600 * 1000), tel]
    );

    sendVerificationCode(tel, otp);
  }
  
  app.post(`${API_PREFIX}/account/enter`, {
    schema: {
      body: {
        type: 'object',
        required: ["tel", "password"],
        properties: {
          tel: { type: 'string' },
          password: { type: 'string' },
        },
      },
    },
    async handler (request, reply) {
      try {
        let [rows, fields] = await dbConn.execute(
          `SELECT * FROM phoneWhitelist WHERE phoneNumber = ?`,
          [request.body.tel],
        );

        if (rows.length != 1) {
          reply.send({
            error: "not-added",
          });
          return;
        }

        [rows, fields] = await dbConn.execute(
          'SELECT * FROM `user` WHERE `id` = ?',
          [request.body.tel]
        );
  
        if (rows.length === 1) {
          const passwordCheck = await argon2.verify(rows[0].password, request.body.password);
          if (!passwordCheck) {
            reply.send({
              error: "user",
            });
            return;
          }

          if (rows[0].verified) {
            reply.send({
              error: null,
              type: "token-issue",
              data: {
                token: await commonFns.issueJwtFromRow(rows[0]),
              },
            });
          }
          else {
            await otpCreate(request.body.tel);
            reply.send({ error: null, type: "otp-verify" });
          }
        }
        else {
          let verified = 0;
          if (!request.body.tel.startsWith("+86")) verified = 1;

          // register account send OTP
          await dbConn.execute(
            "INSERT INTO `user` (`id`, `email`, `password`, `quota`, `tier`, `otp`, `otpExp`, `verified`) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [request.body.tel, "", await argon2.hash(request.body.password), 20, 0, "888888", new Date("01/01/1990"), verified]
          );

          if (verified === 1) {
            [rows, fields] = await dbConn.execute(
              'SELECT * FROM `user` WHERE `id` = ?',
              [request.body.tel]
            );

            reply.send({
              error: null,
              type: "token-issue",
              data: {
                token: await commonFns.issueJwtFromRow(rows[0]),
              },
            });
            return;
          }
  
          await otpCreate(request.body.tel);
          reply.send({ error: null, type: "otp-create-verify" });
        }
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
}

module.exports = { registerAccountAPI };