#!/usr/bin/env node
/**
 * Simple CLI bridge to send a message to OpenClaw gateway and print the response.
 * Usage: node send_message.mjs "Your message here"
 */

import { GatewayClient } from './dist/gateway/client.js';

const message = process.argv[2];
if (!message) {
  console.error('Usage: node send_message.mjs "message"');
  process.exit(1);
}

const GATEWAY_URL = process.env.OPENCLAW_GATEWAY_URL || 'ws://127.0.0.1:18789/ws';
const TOKEN = process.env.OPENCLAW_TOKEN || '7951895c62cb268df323f0846a65f27e0e995ddc26864fbf';

let responseText = '';
let done = false;

const client = new GatewayClient({
  url: GATEWAY_URL,
  token: TOKEN,
  clientName: 'voice-agent',
  clientDisplayName: 'Voice Agent',
  clientVersion: '1.0.0',
  mode: 'cli',
  onHelloOk: async () => {
    // Connected, send the chat message
    try {
      const runId = `voice-${Date.now()}`;
      
      // Listen for chat events
      client.on('chat', (payload) => {
        if (payload.state === 'delta') {
          responseText += payload.text || '';
        } else if (payload.state === 'final') {
          if (payload.message?.content) {
            for (const c of payload.message.content) {
              if (c.type === 'text') {
                responseText = c.text || responseText;
              }
            }
          }
          console.log(responseText);
          done = true;
          client.stop();
        } else if (payload.state === 'error') {
          console.error('Error:', payload.errorMessage);
          done = true;
          client.stop();
        }
      });

      const res = await client.request('chat.send', {
        sessionKey: 'voice-agent',
        message: message,
        idempotencyKey: runId,
      });
      
      if (res?.status === 'error') {
        console.error('Error:', res.summary);
        process.exit(1);
      }
      
      // Wait up to 2 minutes for response
      const timeout = setTimeout(() => {
        if (!done) {
          console.error('Timeout waiting for response');
          client.stop();
          process.exit(1);
        }
      }, 120000);
      timeout.unref();
      
    } catch (err) {
      console.error('Request failed:', err.message);
      client.stop();
      process.exit(1);
    }
  },
  onConnectError: (err) => {
    console.error('Connection failed:', err.message);
    process.exit(1);
  },
  onClose: (code, reason) => {
    if (!done) {
      console.error(`Connection closed (${code}): ${reason}`);
      process.exit(1);
    }
  },
});

client.start();
