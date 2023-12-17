const fetch = require('node-fetch');
const app = require('fastify')({ logger: true })

app.get('/', function handler (request, reply) {
  reply.send({ hello: 'world' })
})

app.listen({ port: 8082 }, (err) => {
  if (err) {
    fastify.log.error(err)
    process.exit(1)
  }
})