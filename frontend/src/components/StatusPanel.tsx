import { Activity, Zap, AlertCircle } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * StatusPanel
 *
 * System health and debugging information.
 * Shows:
 * - Database connection status
 * - Ollama/LLM status
 * - WebSocket connection
 * - VRAM usage (in production)
 * - Last query/edit with intent JSON and SQL
 *
 * Analogy: Like the "Activity Monitor" on macOS - shows what's happening.
 */

export function StatusPanel() {
  const { isConnected } = useWebSocket();

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          <CardTitle>System Status</CardTitle>
        </div>
        <CardDescription>Real-time service health</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* WebSocket */}
        <div className="flex items-center justify-between">
          <span className="text-sm">WebSocket</span>
          <Badge variant={isConnected ? "default" : "destructive"}>
            {isConnected ? "Connected" : "Disconnected"}
          </Badge>
        </div>

        {/* Database */}
        <div className="flex items-center justify-between">
          <span className="text-sm">Database</span>
          <Badge variant="default">Connected</Badge>
        </div>

        {/* Ollama LLM */}
        <div className="flex items-center justify-between">
          <span className="text-sm">Ollama (qwen2.5:3b)</span>
          <Badge variant="default">Ready</Badge>
        </div>

        {/* VRAM (production) */}
        <div className="flex items-center justify-between border-t pt-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-500" />
            <span className="text-sm">VRAM Usage</span>
          </div>
          <span className="text-sm font-mono">~2.8 GB / 4.0 GB</span>
        </div>

        {/* Last operation */}
        <div className="border-t pt-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            Last Operation
          </p>
          <details className="text-xs">
            <summary className="cursor-pointer">Intent JSON</summary>
            <div className="bg-muted p-2 rounded mt-2 font-mono">
              <pre className="text-xs overflow-auto">
{`{
  "operation": "QUERY_HEIGHT",
  "layer": "structures",
  "filter": { "min_height_m": 20 },
  "scope": "preview"
}`}
              </pre>
            </div>
          </details>

          <details className="text-xs">
            <summary className="cursor-pointer">SQL Executed</summary>
            <div className="bg-muted p-2 rounded mt-2 font-mono">
              <pre className="text-xs overflow-auto">
{`SELECT id, height_m, area_m2, region
FROM structures
WHERE height_m > 20
ORDER BY height_m DESC`}
              </pre>
            </div>
          </details>
        </div>

        {/* Warnings */}
        <div className="flex items-start gap-2 border-t pt-3 rounded-lg bg-yellow-50 dark:bg-yellow-950 p-2">
          <AlertCircle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-yellow-800 dark:text-yellow-200">
            Demo mode: Using mock data. Connect to real backend at /api/ for production.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
