/**
 * Quick Chat CLI - Send a message and print the response
 * 
 * Usage:
 *   pnpm openclaw chat "Your message here"
 *   pnpm openclaw chat --session mySession "Hello"
 */

import type { Command } from "commander";
import { theme } from "../terminal/theme.js";
import { GatewayChatClient, type GatewayEvent } from "../tui/gateway-chat.js";

type ChatDeltaPayload = {
  runId: string;
  sessionKey: string;
  state: "delta" | "final" | "error";
  seq: number;
  text?: string;
  message?: {
    role: string;
    content: Array<{ type: string; text?: string }>;
  };
  errorMessage?: string;
};

export function registerChatCli(program: Command) {
  program
    .command("chat <message>")
    .description("Send a chat message and print the response")
    .option("--session <key>", "Session key", "quick-chat")
    .option("--url <url>", "Gateway WebSocket URL")
    .option("--token <token>", "Gateway token")
    .option("--timeout <ms>", "Timeout in ms", "120000")
    .option("--raw", "Print raw response without formatting", false)
    .action(async (message: string, opts) => {
      const sessionKey = opts.session ?? "quick-chat";
      const timeoutMs = parseInt(opts.timeout, 10) || 120000;
      const raw = Boolean(opts.raw);

      const client = new GatewayChatClient({
        url: opts.url,
        token: opts.token,
      });

      let responseText = "";
      let done = false;
      let errorMessage: string | undefined;

      // Listen for chat events
      client.onEvent = (evt: GatewayEvent) => {
        if (evt.event !== "chat") return;
        
        const payload = evt.payload as ChatDeltaPayload | undefined;
        if (!payload) return;

        console.error(`[debug] Chat payload state: ${payload.state}, text length: ${payload.text?.length ?? 0}`);
        
        if (payload.state === "delta") {
          const delta = payload.text ?? "";
          responseText += delta;
          if (!raw) {
            process.stdout.write(delta);
          }
        } else if (payload.state === "final") {
          if (payload.message?.content) {
            for (const c of payload.message.content) {
              if (c.type === "text" && c.text) {
                // Final message may have full text
                if (!responseText) {
                  responseText = c.text;
                }
              }
            }
          }
          done = true;
        } else if (payload.state === "error") {
          errorMessage = payload.errorMessage ?? "Unknown error";
          done = true;
        }
      };

      client.onDisconnected = (reason) => {
        if (!done) {
          console.error(theme.error(`\nDisconnected: ${reason}`));
          process.exit(1);
        }
      };

      // Set up timeout
      const timeout = setTimeout(() => {
        if (!done) {
          console.error(theme.error("\nTimeout waiting for response"));
          client.stop();
          process.exit(1);
        }
      }, timeoutMs);
      timeout.unref();

      try {
        // Connect
        console.error(`[debug] Connecting to gateway...`);
        client.start();
        await client.waitForReady();
        console.error(`[debug] Connected, session: ${sessionKey}`);

        // Send message
        console.error(`[debug] Sending message: ${message.substring(0, 50)}...`);
        const result = await client.sendChat({
          sessionKey,
          message,
          timeoutMs,
        });
        console.error(`[debug] Message sent, runId: ${result.runId}`);

        // Wait for completion
        await new Promise<void>((resolve) => {
          const check = () => {
            if (done) {
              resolve();
            } else {
              setTimeout(check, 100);
            }
          };
          check();
        });

        console.error(`[debug] Done, responseText length: ${responseText.length}`);

        // Output result
        if (raw && responseText) {
          console.log(responseText);
        } else if (!raw) {
          console.log(); // Newline after streaming
        }

        if (errorMessage) {
          console.error(theme.error(`Error: ${errorMessage}`));
          process.exit(1);
        }

        client.stop();
        clearTimeout(timeout);
        process.exit(0);
      } catch (err) {
        console.error(theme.error(`Failed: ${err instanceof Error ? err.message : String(err)}`));
        client.stop();
        process.exit(1);
      }
    });
}
