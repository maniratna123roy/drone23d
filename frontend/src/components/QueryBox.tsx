import { Send, Loader2, Sparkles, Database, X } from "lucide-react";
import { useState } from "react";
import { useSpatialStore } from "@/store/spatialStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

/**
 * QueryBox
 *
 * Natural language query interface wired to the FastAPI AI agent loop.
 *
 * Beginner Analogy:
 * The voice assistant for your 3D city:
 * You ask "Which buildings are taller than 20 metres?", the local AI turns your question into
 * an exact PostGIS database query, filters the buildings instantly, and lights them up in radiant amber in 3D.
 */

import { API_BASE_URL } from "@/lib/api";

interface QueryResultItem {
  id: string;
  label: string;
  layer: string;
  height: number;
  area: number;
  region: string;
}

export function QueryBox() {
  const {
    setHighlightedObjectIds,
    setSelectedObjectId,
    setQueryFilterActive,
    queryFilterActive,
  } = useSpatialStore();
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<QueryResultItem[]>([]);
  const [sqlExecuted, setSqlExecuted] = useState("");
  const [metrics, setMetrics] = useState<{
    count: number;
    avg_height_m: number;
    total_area_m2: number;
  } | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setErrorMsg("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: query }),
      });

      if (!response.ok) {
        throw new Error(`Query failed: HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log("[QueryBox] Backend response:", data);

      if (data.matched_ids && Array.isArray(data.matched_ids)) {
        const idStrings = data.matched_ids.map((id: number | string) => String(id));
        setHighlightedObjectIds(idStrings);
        setQueryFilterActive(true);

        const items: QueryResultItem[] = (data.objects || []).map((obj: any) => ({
          id: String(obj.id),
          label: `Building #${obj.id}`,
          layer: obj.class_name || "structures",
          height: Number(obj.height_m || 0),
          area: Number(obj.area_m2 || 0),
          region: obj.region || "CENTER",
        }));

        setResults(items);
        setSqlExecuted(data.sql || "");
        setMetrics(data.metrics || null);
      } else {
        setResults([]);
        setHighlightedObjectIds([]);
        setQueryFilterActive(false);
        setSqlExecuted(data.sql || "");
        setMetrics(null);
      }
    } catch (err: any) {
      console.error("[QueryBox] Execution failed:", err);
      setErrorMsg(err.message || "Failed to communicate with AI query service");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickQuery = (example: string) => {
    setQuery(example);
  };

  const clearQuery = () => {
    setQuery("");
    setResults([]);
    setSqlExecuted("");
    setMetrics(null);
    setErrorMsg("");
    setHighlightedObjectIds([]);
    setQueryFilterActive(false);
    setSelectedObjectId(null);
  };

  return (
    <Card className="w-full shadow-sm border-border/60">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber-500" />
          <CardTitle className="text-sm font-semibold">Spatial AI Query</CardTitle>
        </div>
        <CardDescription className="text-xs">
          Ask questions in plain English (e.g., &quot;Which buildings &gt; 20m?&quot;)
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Query input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            placeholder="Type query or select an example below..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
            className="flex-1 text-xs h-9 bg-background/50"
          />
          <Button
            type="submit"
            disabled={isLoading || !query.trim()}
            size="sm"
            className="h-9 px-3 gap-1.5"
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <>
                <Send className="h-3.5 w-3.5" />
                <span className="text-xs hidden sm:inline">Ask</span>
              </>
            )}
          </Button>
          {queryFilterActive && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={clearQuery}
              className="h-9 px-2 gap-1"
              title="Clear query and show all buildings"
            >
              <X className="h-3.5 w-3.5" />
              <span className="text-xs hidden sm:inline">Clear</span>
            </Button>
          )}
        </form>

        {/* Canned Quick Queries for 5-minute Judge Demo */}
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => handleQuickQuery("Which buildings are taller than 20 metres?")}
            className="text-[11px] px-2 py-0.5 rounded-full bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            Taller than 20m
          </button>
          <button
            type="button"
            onClick={() => handleQuickQuery("Show all buildings in the north region")}
            className="text-[11px] px-2 py-0.5 rounded-full bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            North region
          </button>
          <button
            type="button"
            onClick={() => handleQuickQuery("Buildings between 25 and 40 metres")}
            className="text-[11px] px-2 py-0.5 rounded-full bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            Between 25m & 40m
          </button>
        </div>

        {errorMsg && (
          <div className="p-2 rounded bg-destructive/10 text-destructive text-xs">
            {errorMsg}
          </div>
        )}

        {/* Results summary & table */}
        {results.length > 0 && (
          <div className="space-y-2 pt-2 border-t">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">
                Matched: {results.length} buildings
              </span>
              {metrics && (
                <span className="text-[11px] text-muted-foreground">
                  Avg: {metrics.avg_height_m}m | Area: {metrics.total_area_m2}m²
                </span>
              )}
            </div>

            <div className="border rounded-md overflow-hidden max-h-48 overflow-y-auto">
              <Table className="text-[11px]">
                <TableHeader>
                  <TableRow className="h-7">
                    <TableHead className="py-1">Building</TableHead>
                    <TableHead className="py-1">Region</TableHead>
                    <TableHead className="py-1 text-right">Height</TableHead>
                    <TableHead className="py-1 text-right">Area</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((r) => (
                    <TableRow
                      key={r.id}
                      onClick={() => setSelectedObjectId(r.id)}
                      className="cursor-pointer hover:bg-amber-500/10 h-7 transition-colors"
                    >
                      <TableCell className="py-1 font-medium text-amber-400">
                        {r.label}
                      </TableCell>
                      <TableCell className="py-1">
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5">
                          {r.region}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-1 text-right font-mono">
                        {r.height.toFixed(1)}m
                      </TableCell>
                      <TableCell className="py-1 text-right font-mono text-muted-foreground">
                        {r.area.toFixed(0)}m²
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Expandable Parameterized SQL */}
            {sqlExecuted && (
              <details className="text-[11px] bg-muted/40 rounded p-2">
                <summary className="cursor-pointer font-medium text-muted-foreground flex items-center gap-1.5 select-none">
                  <Database className="h-3 w-3" />
                  <span>Compiled PostGIS SQL</span>
                </summary>
                <pre className="mt-1.5 p-2 bg-background/80 rounded border font-mono text-[10px] whitespace-pre-wrap overflow-x-auto text-emerald-400">
                  {sqlExecuted}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && results.length === 0 && queryFilterActive && !errorMsg && (
          <div className="text-center py-4 text-amber-300 text-xs">
            No buildings matched this query. Clear the query to show all buildings.
          </div>
        )}
        {!isLoading && results.length === 0 && !queryFilterActive && !errorMsg && (
          <div className="text-center py-4 text-muted-foreground text-xs">
            Ask a question above to highlight matching 3D structures in the twin.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
