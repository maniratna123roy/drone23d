import React, { useRef, useState } from "react";
import { Upload, FileVideo, Compass, Play, AlertCircle, CheckCircle2 } from "lucide-react";

interface VideoUploaderProps {
  onStartReconstruction: (videoFile: File | null, gpsFile: File | null) => void;
  disabled?: boolean;
}

export const VideoUploader: React.FC<VideoUploaderProps> = ({
  onStartReconstruction,
  disabled = false,
}) => {
  const videoInputRef = useRef<HTMLInputElement>(null);
  const gpsInputRef = useRef<HTMLInputElement>(null);

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [gpsFile, setGpsFile] = useState<File | null>(null);
  const [videoMetadata, setVideoMetadata] = useState<{
    name: string;
    sizeMb: string;
    durationEstimate: string;
  } | null>(null);

  const handleVideoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
      setVideoMetadata({
        name: file.name,
        sizeMb: (file.size / (1024 * 1024)).toFixed(1),
        durationEstimate: "Continuous orbital drone pass",
      });
    }
  };

  const handleGpsSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setGpsFile(file);
    }
  };

  const handleLoadSampleFlight = () => {
    // Simulated drone capture file for testing
    setVideoFile(null);
    setVideoMetadata({
      name: "mill19_orbital_drone_pass_4k.mp4",
      sizeMb: "48.2",
      durationEstimate: "2m 14s (30 fps, 4K UHD)",
    });
    setGpsFile(new File(["[latitude: 26.1872] [longitude: 91.6914] [altitude: 124.5]"], "mill19_telemetry.srt", { type: "text/plain" }));
  };

  return (
    <div className="rounded-lg border border-border/80 bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
            1. Drone Video & Telemetry Input
          </h2>
          <p className="text-xs text-muted-foreground">
            Provide a single continuous drone video pass (MP4 / MOV) and optional companion DJI SRT or GPS file.
          </p>
        </div>

        <button
          type="button"
          disabled={disabled}
          onClick={handleLoadSampleFlight}
          className="text-xs font-mono text-purple-400 hover:text-purple-300 underline underline-offset-4 disabled:opacity-50"
        >
          Load Verified Drone Sample Pass
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Video Upload Area */}
        <div
          onClick={() => !disabled && videoInputRef.current?.click()}
          className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg text-center transition-colors cursor-pointer ${
            videoMetadata
              ? "border-purple-500/60 bg-purple-500/5"
              : "border-border/60 hover:border-purple-500/50 hover:bg-muted/20"
          } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <input
            ref={videoInputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska"
            className="hidden"
            onChange={handleVideoSelect}
            disabled={disabled}
          />

          <FileVideo className="h-8 w-8 text-purple-400 mb-2" />
          {videoMetadata ? (
            <div>
              <p className="text-xs font-semibold text-foreground">{videoMetadata.name}</p>
              <p className="text-[11px] font-mono text-purple-300 mt-1">
                {videoMetadata.sizeMb} MB · {videoMetadata.durationEstimate}
              </p>
              <p className="text-[10px] text-muted-foreground mt-2">Click to replace video</p>
            </div>
          ) : (
            <div>
              <p className="text-xs font-medium text-foreground">Click to upload Drone Video</p>
              <p className="text-[11px] text-muted-foreground mt-1">H.264 / HEVC MP4 or MOV</p>
            </div>
          )}
        </div>

        {/* GPS / Telemetry Upload Area */}
        <div
          onClick={() => !disabled && gpsInputRef.current?.click()}
          className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg text-center transition-colors cursor-pointer ${
            gpsFile
              ? "border-emerald-500/60 bg-emerald-500/5"
              : "border-border/60 hover:border-emerald-500/50 hover:bg-muted/20"
          } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <input
            ref={gpsInputRef}
            type="file"
            accept=".srt,.json,.gpx,.csv"
            className="hidden"
            onChange={handleGpsSelect}
            disabled={disabled}
          />

          <Compass className="h-8 w-8 text-emerald-400 mb-2" />
          {gpsFile ? (
            <div>
              <p className="text-xs font-semibold text-foreground">{gpsFile.name}</p>
              <p className="text-[11px] font-mono text-emerald-400 mt-1">
                GPS Prior Loaded · Metric Scale Enforced
              </p>
              <p className="text-[10px] text-muted-foreground mt-2">Click to replace GPS file</p>
            </div>
          ) : (
            <div>
              <p className="text-xs font-medium text-foreground">Companion DJI .SRT or GPS File (Optional)</p>
              <p className="text-[11px] text-muted-foreground mt-1">
                Enables Umeyama metric scaling without Ground Control Points
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3.5 w-3.5 text-purple-400" />
          <span>Zero Ground Control Points required (automated camera auto-calibration).</span>
        </div>

        <button
          type="button"
          disabled={disabled || (!videoFile && !videoMetadata)}
          onClick={() => onStartReconstruction(videoFile, gpsFile)}
          className="flex items-center gap-2 rounded bg-purple-600 px-5 py-2 font-mono text-xs font-medium text-white hover:bg-purple-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-purple-600/20"
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span>Launch Videogrammetry Pipeline</span>
        </button>
      </div>
    </div>
  );
};
