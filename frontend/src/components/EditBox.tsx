import { Send, Loader2, Undo2 } from "lucide-react";
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
import { Alert, AlertDescription } from "@/components/ui/alert";

/**
 * EditBox
 *
 * Natural language edit interface with preview & confirm flow.
 * User types: "Raise the two central buildings by 40 metres"
 * 
 * Flow:
 * 1. Parse intent
 * 2. Generate preview (ghost overlay)
 * 3. User confirms
 * 4. Apply changes to DB
 * 5. Broadcast to all clients via WebSocket
 * 6. Undo stack updated
 *
 * Analogy: Like a non-destructive edit in Photoshop - preview before committing.
 */

import { API_BASE_URL } from "@/lib/api";

export function EditBox() {
  const {
    objects,
    setGhostObjects,
    clearGhostObjects,
    setPreviewToken,
    previewToken,
    addHiddenBbox,
    setHiddenBboxes,
    setObjects,
  } = useSpatialStore();

  const [edit, setEdit] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [preview, setPreview] = useState<{
    command: string;
    affectedCount: number;
    deltaM: number;
  } | null>(null);
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!edit.trim()) return;

    setIsLoading(true);
    setMessage("");

    try {
      console.log(`[EditBox] Requesting preview for: "${edit}"`);
      const res = await fetch(`${API_BASE_URL}/api/edit/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: edit }),
      });

      const data = await res.json();

      if (data.status === "success" && data.preview_token) {
        setPreviewToken(data.preview_token);

        // Convert deltas into 3D Ghost objects
        const ghosts = (data.deltas || []).map((d: any) => {
          const match = objects.find((o) => o.id === String(d.object_id));
          return {
            id: String(d.object_id),
            originalHeight: d.current_height_m,
            newHeight: d.new_height_m,
            deltaHeight: d.delta_height_m,
            elevationM: match?.elevationM || 0,
            x: match?.x || 0,
            z: match?.z || 0,
            width: match?.width || 10,
            depth: match?.depth || 10,
            footprint: d.footprint || match?.footprint,
          };
        });

        setGhostObjects(ghosts);

        const deltaVal = data.deltas?.[0]?.delta_height_m ?? 10;
        setPreview({
          command: edit,
          affectedCount: data.affected_count,
          deltaM: deltaVal,
        });
        setMessage(`Previewing: ${data.message}`);
      } else {
        setMessage(data.message || "Could not generate preview.");
      }
    } catch (error) {
      console.error("[EditBox] Preview failed:", error);
      setMessage("Failed to connect to edit service.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!previewToken) return;

    setIsLoading(true);

    try {
      console.log(`[EditBox] Confirming edit with token: ${previewToken}`);
      const res = await fetch(`${API_BASE_URL}/api/edit/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preview_token: previewToken }),
      });

      const data = await res.json();

      if (data.status === "success") {
        // Mask out old splats in the edited structures' bounding boxes
        (data.updated_objects || []).forEach((s: any) => {
          if (s.splat_bbox) {
            addHiddenBbox(s.splat_bbox);
          }
        });

        clearGhostObjects();
        setPreview(null);
        setEdit("");
        setMessage(`✓ ${data.message}`);
        setTimeout(() => setMessage(""), 4000);
      } else {
        setMessage(`Failed: ${data.message}`);
      }
    } catch (error) {
      console.error("[EditBox] Apply failed:", error);
      setMessage("Failed to apply changes to database.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    clearGhostObjects();
    setPreview(null);
    setMessage("");
  };

  const handleUndo = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/edit/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.status === "success") {
        // Clear masked bounding boxes so original splats are restored
        setHiddenBboxes([]);
        setMessage(`✓ ${data.message}`);
      } else {
        setMessage(data.message || "Nothing to undo.");
      }
      setTimeout(() => setMessage(""), 3500);
    } catch (err) {
      console.error("[EditBox] Undo failed:", err);
      setMessage("Failed to undo last edit.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Natural Language Edit</CardTitle>
        <CardDescription>
          Modify your scene with commands like &quot;Raise the building by 10
          metres&quot;
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Edit input */}
        {!preview && (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              placeholder="e.g., 'Raise the central buildings by 40 metres'"
              value={edit}
              onChange={(e) => setEdit(e.target.value)}
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={isLoading || !edit.trim()}
              size="icon"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
        )}

        {/* Preview mode */}
        {preview && (
          <div className="space-y-3 border-t pt-4">
            <Alert>
              <AlertDescription>
                <p className="font-medium mb-2">Preview: {preview.command}</p>
                <p className="text-sm">
                  Affects {preview.affectedCount} object
                  {preview.affectedCount !== 1 ? "s" : ""}. Ghost overlay shows
                  the changes.
                </p>
              </AlertDescription>
            </Alert>

            <div className="flex gap-2">
              <Button
                onClick={handleConfirm}
                disabled={isLoading}
                className="flex-1"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Applying...
                  </>
                ) : (
                  "Confirm"
                )}
              </Button>
              <Button
                onClick={handleCancel}
                variant="outline"
                disabled={isLoading}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Undo button */}
        <div className="flex gap-2">
          <Button
            onClick={handleUndo}
            disabled={isLoading}
            variant="outline"
            size="sm"
            className="w-full"
          >
            <Undo2 className="h-4 w-4 mr-2" />
            Undo Last Change
          </Button>
        </div>

        {/* Status message */}
        {message && (
          <div className="text-sm text-center font-medium text-green-600 bg-green-50 p-2 rounded">
            {message}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
