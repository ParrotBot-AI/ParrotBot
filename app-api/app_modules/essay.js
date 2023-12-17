const fetch = require('node-fetch');
const app = require('fastify')()
const mysql = require('mysql2/promise');
const argon2 = require('argon2');
const jwt = require('jsonwebtoken');
const fs = require("fs");

async function registerEssayAPI(app, dbConn, commonFns, API_PREFIX) {
  app.post(`${API_PREFIX}/essay/deleteTopicBookmark`, {
    schema: {
      body: {
        type: 'object',
        required: ["topicId"],
        properties: {
          topicId: { type: 'number' },
        },
      },
    },
    async handler(request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }

        await dbConn.execute(
          `DELETE FROM essayTopicBookmark WHERE user = ? AND essayTopic = ?`,
          [user.uid, request.body.topicId],
        );
  
        reply.send({ error: null });
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });

  app.post(`${API_PREFIX}/essay/addTopicBookmark`, {
    schema: {
      body: {
        type: 'object',
        required: ["topicId"],
        properties: {
          topicId: { type: 'number' },
        },
      },
    },
    async handler(request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }

        await dbConn.execute(
          `INSERT INTO essayTopicBookmark (user, essayTopic) VALUES (?, ?)`,
          [user.uid, request.body.topicId],
        );
  
        reply.send({ error: null });
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
  
  app.get(`${API_PREFIX}/essay/essayDetails/:topicId`, {
    async handler (request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }
        
        const response = { error: null, data: {} };

        const { topicId } = request.params;

        let [rows, fields] = await dbConn.execute(
          `SELECT prompt, promptFull FROM essayTopic WHERE id = ?`,
          [topicId],
        );

        response.data = JSON.parse(JSON.stringify(rows[0]));

        [rows, fields] = await dbConn.execute(
          `SELECT essay.id, essayTopic.id AS topicId, prompt, inferenceResult, content, essay.timestamp, essay.version, essay.score FROM essay
LEFT OUTER JOIN essayTopic ON essayTopic.id = essay.essayTopic WHERE essay.user = ? AND essay.essayTopic = ?
ORDER BY id DESC`,
          [user.uid, topicId],
        );

        response.data.attempts = rows;

        reply.send(response);
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
  
  app.get(`${API_PREFIX}/essay/essaySummary`, {
    async handler (request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }

        const [rows, fields] = await dbConn.execute(
          `SELECT essay.id, essayTopic.id AS topicId, prompt, LEFT(inferenceResult, 7) as status, LEFT(content, 100) as preview, essay.timestamp, essay.version, essay.score FROM essay
LEFT OUTER JOIN essayTopic ON essayTopic.id = essay.essayTopic WHERE essay.user = ?
ORDER BY id DESC`,
          [user.uid],
        );

        reply.send({ error: null, data: rows });
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });

  app.post(`${API_PREFIX}/essay/submitAttempt`, {
    schema: {
      body: {
        type: 'object',
        required: ["topicId", "content"],
        properties: {
          topicId: { type: 'number' },
          content: { type: 'string' },
        },
      },
    },
    async handler(request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }
  
        // TODO: basic input sanitisation using vector distance
        // WORD LIMIT?
  
        // END TODO
  
        let [rows, fields] = await dbConn.execute(`SELECT quota FROM user WHERE id = ?`, [user.uid]);
        if (rows[0].quota < 1) {
          reply.send({ error: "quota" });
          return;
        }

        await dbConn.execute(`UPDATE user SET quota = ? WHERE id = ?`, [rows[0].quota - 1, user.uid]);
        
        [rows, fields] = await dbConn.execute(`SELECT COUNT(id) as versions FROM essay WHERE essay.user = ? AND essay.essayTopic = ?`, [user.uid, request.body.topicId]);
  
        [rows, fields] = await dbConn.execute(
          "INSERT INTO `essay` (`user`, `essayTopic`, `content`, `version`, `inferenceResult`, `meta`, `score`, `maxScore`) VALUES (?, ?, ?, ?, 'pending', '{}', -1, -1)",
          [user.uid, request.body.topicId, request.body.content, rows[0].versions + 1]
        );

        const insertedEssayId = rows.insertId;

        [rows, fields] = await dbConn.execute(`SELECT promptFull FROM essayTopic WHERE id = ?`, [request.body.topicId]);
  
        // INFERENCE REQUEST
        let inferenceRequest = {
          discussion: rows[0].promptFull.substring(rows[0].promptFull.indexOf("Professor")),
          content: request.body.content,
        };
        console.log(inferenceRequest);

        let inferenceResponse = await fetch("http://localhost:8000/fastapi/evaluateEssay", {
          method: "post",
          body: JSON.stringify(inferenceRequest),
          headers: {
            "parrot2": "a62a39c5-b710-49ce-9a8a-72537a810e27",
            "content-type": "application/json",
          }
        }).then(res => res.text());
        await dbConn.execute(`UPDATE essay SET inferenceResult = ? WHERE id = ?`, [inferenceResponse, insertedEssayId]);
  
        reply.send({ error: null });
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
  
  app.get(`${API_PREFIX}/essay/topicSummary`, {
    async handler (request, reply) {
      try {
        if (!request.headers.authorization) {
          reply.send({ error: "token" });
          return;
        }
  
        const user = await commonFns.verifyJwt(request.headers.authorization);
        if (!user) {
          reply.send({ error: "token" });
          return;
        }

        const [rows, fields] = await dbConn.execute(
          `WITH unionResult AS (
SELECT essayTopic.id, MAX(essay.id) AS objId, prompt, promptFull, NULL as bookmarkUser, MAX(essay.timestamp) AS essayTimestamp, MAX(essay.version) as essayVersion FROM essay
INNER JOIN essayTopic ON essayTopic.id = essay.essayTopic AND essay.user = ? GROUP BY id, prompt
UNION
SELECT essayTopic.id, essayTopicBookmark.id as objId, prompt, promptFull, user AS bookmarkUser, NULL as essayTimestamp, NULL as essayVersion FROM essayTopic 
LEFT OUTER JOIN essayTopicBookmark ON essayTopicBookmark.essayTopic = essayTopic.id AND essayTopicBookmark.user = ?
)
SELECT id, prompt, promptFull, objId, MAX(bookmarkUser) as bookmarkUser, MAX(essayTimestamp) as essayTimestamp, MAX(essayVersion) as essayVersion FROM unionResult
WHERE id IS NOT NULL
GROUP BY id, prompt ORDER BY essayTimestamp DESC`,
          [user.uid, user.uid],
        );

        reply.send({ error: null, data: rows });
      }
      catch (e) {
        console.log(e);
        reply.send({ error: "error" });
      }
    },
  });
}

module.exports = { registerEssayAPI };