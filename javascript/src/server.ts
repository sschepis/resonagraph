#!/usr/bin/env node
/**
 * ResonaGraph Server - RPC Node
 * 
 * Provides HTTP/WebSocket API for ResonaGraph operations.
 */

import express, { Express, Request, Response } from 'express';
import { Server as WebSocketServer } from 'ws';
import * as http from 'http';
import { Client, PhaseKey } from './index';

const DEFAULT_PORT = 8443;
const DEFAULT_HOST = '0.0.0.0';

interface ServerConfig {
  port: number;
  host: string;
  enableWebSocket: boolean;
}

export class ResonaGraphServer {
  private app: Express;
  private server: http.Server;
  private wss?: WebSocketServer;
  private client: Client;
  private config: ServerConfig;

  constructor(config: Partial<ServerConfig> = {}) {
    this.config = {
      port: config.port ?? DEFAULT_PORT,
      host: config.host ?? DEFAULT_HOST,
      enableWebSocket: config.enableWebSocket ?? true,
    };

    this.app = express();
    this.server = http.createServer(this.app);
    this.client = new Client(`http://localhost:${this.config.port}`);

    this.setupMiddleware();
    this.setupRoutes();

    if (this.config.enableWebSocket) {
      this.setupWebSocket();
    }
  }

  private setupMiddleware(): void {
    // Parse JSON bodies
    this.app.use(express.json());

    // CORS headers
    this.app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Phase-Key');
      if (req.method === 'OPTIONS') {
        res.sendStatus(200);
      } else {
        next();
      }
    });

    // Request logging
    this.app.use((req, res, next) => {
      console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
      next();
    });
  }

  private setupRoutes(): void {
    // Health check
    this.app.get('/health', (req: Request, res: Response) => {
      res.json({
        status: 'ok',
        version: '0.1.0',
        timestamp: new Date().toISOString(),
      });
    });

    // Stats endpoint
    this.app.get('/stats', (req: Request, res: Response) => {
      const stats = this.client.getStats();
      res.json(stats);
    });

    // PUT operation
    this.app.post('/v1/put', (req: Request, res: Response) => {
      try {
        const { key, payload, options } = req.body;
        const phaseKeySecret = req.headers['x-phase-key'] as string || 'default-secret';
        
        if (!key || !payload) {
          res.status(400).json({ error: 'Missing key or payload' });
          return;
        }

        const phaseKey = PhaseKey.fromPassphrase(phaseKeySecret);
        const beacon = this.client.put(key, payload, phaseKey, options);

        res.json({
          success: true,
          beacon,
        });
      } catch (error) {
        console.error('PUT error:', error);
        res.status(500).json({
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    });

    // GET operation
    this.app.post('/v1/get', (req: Request, res: Response) => {
      try {
        const { key, options } = req.body;
        const phaseKeySecret = req.headers['x-phase-key'] as string || 'default-secret';
        
        if (!key) {
          res.status(400).json({ error: 'Missing key' });
          return;
        }

        const phaseKey = PhaseKey.fromPassphrase(phaseKeySecret);
        const result = this.client.get(key, phaseKey, options);

        res.json({
          success: true,
          payload: result.payload,
          metrics: result.metrics,
        });
      } catch (error) {
        console.error('GET error:', error);
        res.status(500).json({
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    });

    // Query operation (placeholder)
    this.app.post('/v1/query', (req: Request, res: Response) => {
      res.status(501).json({
        success: false,
        error: 'Query operation not yet implemented',
      });
    });
  }

  private setupWebSocket(): void {
    this.wss = new WebSocketServer({ server: this.server });

    this.wss.on('connection', (ws) => {
      console.log('WebSocket client connected');

      ws.on('message', (message: string) => {
        try {
          const data = JSON.parse(message.toString());
          
          // Handle different message types
          switch (data.type) {
            case 'ping':
              ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
              break;
            default:
              ws.send(JSON.stringify({ type: 'error', message: 'Unknown message type' }));
          }
        } catch (error) {
          ws.send(JSON.stringify({
            type: 'error',
            message: error instanceof Error ? error.message : 'Unknown error',
          }));
        }
      });

      ws.on('close', () => {
        console.log('WebSocket client disconnected');
      });
    });
  }

  start(): void {
    this.server.listen(this.config.port, this.config.host, () => {
      console.log('╔════════════════════════════════════════════════════════╗');
      console.log('║         ResonaGraph Server - RPC Node                 ║');
      console.log('╚════════════════════════════════════════════════════════╝');
      console.log(`\nServer running at http://${this.config.host}:${this.config.port}`);
      console.log(`WebSocket: ${this.config.enableWebSocket ? 'Enabled' : 'Disabled'}`);
      console.log('\nEndpoints:');
      console.log(`  GET  /health       - Health check`);
      console.log(`  GET  /stats        - Server statistics`);
      console.log(`  POST /v1/put       - Store data`);
      console.log(`  POST /v1/get       - Retrieve data`);
      console.log(`  POST /v1/query     - Execute query (NYI)`);
      console.log('\nPress Ctrl+C to stop\n');
    });
  }

  stop(): void {
    this.server.close();
    if (this.wss) {
      this.wss.close();
    }
  }
}

// CLI entry point
if (require.main === module) {
  const port = parseInt(process.env.PORT || String(DEFAULT_PORT));
  const host = process.env.HOST || DEFAULT_HOST;

  const server = new ResonaGraphServer({ port, host });
  server.start();

  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log('\nShutting down gracefully...');
    server.stop();
    process.exit(0);
  });
}

export default ResonaGraphServer;
