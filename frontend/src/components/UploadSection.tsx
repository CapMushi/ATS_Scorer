import React, { useRef } from "react";
import { InteractiveHoverButton } from "@/registry/magicui/interactive-hover-button";
import { ChevronDown, FileCheck, X, FileText, Trash2, RefreshCw, Plus } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import SpecularButton from "@/components/SpecularButton";
import { cn } from "@/lib/utils";

export function formatFileSize(bytes: number) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

interface UploadSectionProps {
  jdFile: File | null;
  cvFiles: File[];
  isParsingJd: boolean;
  showJdDropdown: boolean;
  setShowJdDropdown: (val: boolean) => void;
  showCvDropdown: boolean;
  setShowCvDropdown: (val: boolean) => void;
  handleJdUpload: (file: File) => void;
  handleAddCvFiles: (files: FileList | File[]) => void;
  handleRemoveJdFile: () => void;
  handleRemoveCvFile: (idx: number) => void;
  handleClearAllCvs: () => void;
  onOpenEmailImport: () => void;
}

export default function UploadSection({
  jdFile,
  cvFiles,
  isParsingJd,
  showJdDropdown,
  setShowJdDropdown,
  showCvDropdown,
  setShowCvDropdown,
  handleJdUpload,
  handleAddCvFiles,
  handleRemoveJdFile,
  handleRemoveCvFile,
  handleClearAllCvs,
  onOpenEmailImport
}: UploadSectionProps) {
  const jdInputRef = useRef<HTMLInputElement>(null);
  const cvInputRef = useRef<HTMLInputElement>(null);
  const jdDropdownRef = useRef<HTMLDivElement>(null);
  const cvDropdownRef = useRef<HTMLDivElement>(null);

  return (
    <div className="flex gap-4 mt-8 lg:mt-0 items-center">
      {/* Hidden File Inputs */}
      <input
        type="file"
        ref={jdInputRef}
        className="hidden"
        accept=".pdf,.docx,.txt"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleJdUpload(e.target.files[0]);
          }
        }}
      />
      <input
        type="file"
        ref={cvInputRef}
        className="hidden"
        multiple
        accept=".pdf,.docx,.txt"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleAddCvFiles(e.target.files);
          }
        }}
      />

      {/* JD Button & Dropdown */}
      <div className="relative" ref={jdDropdownRef}>
        <div className="flex items-center bg-white/[0.03] rounded-full border border-white/10 p-1 backdrop-blur-sm transition-all hover:bg-white/[0.05] hover:border-amber-500/40 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)]">
          <InteractiveHoverButton
            text={isParsingJd ? "Parsing..." : jdFile ? "JD Loaded ✓" : "Upload JD"}
            loaderColor="amber"
            className="!border-0 !bg-transparent"
            onClick={() => {
              if (!jdFile) {
                jdInputRef.current?.click();
              } else {
                setShowJdDropdown(!showJdDropdown);
              }
            }}
            disabled={isParsingJd}
          />
          {jdFile && (
            <button
              onClick={() => setShowJdDropdown(!showJdDropdown)}
              className="pr-3 pl-0.5 py-1.5 text-muted-foreground hover:text-amber-400 transition-all active:scale-95 flex items-center justify-center cursor-pointer"
              title="JD Options & Controls"
            >
              <ChevronDown size={14} className={cn("transition-transform duration-200", showJdDropdown && "rotate-180")} />
            </button>
          )}
        </div>

        {/* JD Dropdown Menu */}
        <AnimatePresence>
          {showJdDropdown && jdFile && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="absolute right-0 mt-3 w-72 p-4 rounded-2xl bg-black/90 border border-amber-500/30 backdrop-blur-xl shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 flex flex-col gap-3"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                  <FileCheck size={14} /> Active Job Description
                </span>
                <button
                  onClick={() => setShowJdDropdown(false)}
                  className="text-muted-foreground hover:text-foreground p-1 rounded-md"
                >
                  <X size={14} />
                </button>
              </div>

              <div className="flex items-center gap-3 bg-white/[0.04] p-3 rounded-xl border border-white/5">
                <FileText size={20} className="text-amber-400 shrink-0" />
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-xs font-bold text-foreground truncate" title={jdFile.name}>
                    {jdFile.name}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {formatFileSize(jdFile.size)}
                  </span>
                </div>
              </div>

              <div className="flex gap-2 mt-1">
                <SpecularButton
                  size="sm"
                  baseColor="#141008"
                  lineColor="#f59e0b"
                  textColor="#fbbf24"
                  onClick={() => {
                    setShowJdDropdown(false);
                    jdInputRef.current?.click();
                  }}
                  className="flex-1 !py-1.5 !px-3 text-xs font-bold rounded-lg flex items-center justify-center gap-1 cursor-pointer"
                >
                  <RefreshCw size={12} /> Replace JD
                </SpecularButton>

                <button
                  onClick={handleRemoveJdFile}
                  className="p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500 hover:text-white transition-all active:scale-95 flex items-center justify-center cursor-pointer"
                  title="Remove JD"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Import from Email Button */}
      <div className="relative">
        <div className="flex items-center bg-white/[0.03] rounded-full border border-white/10 p-1 backdrop-blur-sm transition-all hover:bg-white/[0.05] hover:border-emerald-500/40 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)]">
          <InteractiveHoverButton
            text="Import from Gmail"
            loaderColor="green"
            className="!border-0 !bg-transparent text-emerald-400"
            onClick={onOpenEmailImport}
          />
        </div>
      </div>

      {/* CVs Button & Dropdown */}
      <div className="relative" ref={cvDropdownRef}>
        <div className="flex items-center bg-white/[0.03] rounded-full border border-white/10 p-1 backdrop-blur-sm transition-all hover:bg-white/[0.05] hover:border-emerald-500/40 shadow-[inset_0_1px_2px_rgba(255,255,255,0.05)]">
          <InteractiveHoverButton
            text={cvFiles.length > 0 ? `${cvFiles.length} CVs ✓` : "Upload CVs"}
            loaderColor="green"
            className="!border-0 !bg-transparent"
            onClick={() => {
              if (cvFiles.length === 0) {
                cvInputRef.current?.click();
              } else {
                setShowCvDropdown(!showCvDropdown);
              }
            }}
          />
          {cvFiles.length > 0 && (
            <button
              onClick={() => setShowCvDropdown(!showCvDropdown)}
              className="pr-3 pl-0.5 py-1.5 text-muted-foreground hover:text-emerald-400 transition-all active:scale-95 flex items-center justify-center cursor-pointer"
              title="CV Batch Controls"
            >
              <ChevronDown size={14} className={cn("transition-transform duration-200", showCvDropdown && "rotate-180")} />
            </button>
          )}
        </div>

        {/* CVs Dropdown Menu */}
        <AnimatePresence>
          {showCvDropdown && cvFiles.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="absolute right-0 mt-3 w-80 p-4 rounded-2xl bg-black/90 border border-emerald-500/30 backdrop-blur-xl shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 flex flex-col gap-3"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider">
                    CV Batch ({cvFiles.length})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleClearAllCvs}
                    className="text-[10px] text-red-400 hover:text-red-300 font-mono uppercase px-2 py-0.5 rounded bg-red-500/10 border border-red-500/20 active:scale-95 transition-all"
                  >
                    Clear All
                  </button>
                  <button
                    onClick={() => setShowCvDropdown(false)}
                    className="text-muted-foreground hover:text-foreground p-1 rounded-md"
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              {/* Scrollable File List */}
              <div className="flex flex-col gap-2 max-h-56 overflow-y-auto pr-1 custom-scrollbar">
                {cvFiles.map((file, idx) => (
                  <div
                    key={`${file.name}_${file.size}_${idx}`}
                    className="flex items-center justify-between gap-2 bg-white/[0.03] p-2.5 rounded-xl border border-white/5 hover:border-emerald-500/30 hover:bg-white/[0.06] transition-all group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <span className="text-[10px] font-mono text-muted-foreground w-4">#{idx + 1}</span>
                      <FileText size={16} className="text-emerald-400 shrink-0" />
                      <div className="flex flex-col min-w-0 flex-1">
                        <span className="text-xs font-semibold text-foreground truncate" title={file.name}>
                          {file.name}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {formatFileSize(file.size)}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => handleRemoveCvFile(idx)}
                      className="opacity-70 group-hover:opacity-100 p-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all active:scale-95 cursor-pointer"
                      title="Remove CV"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Add More CVs Button */}
              <SpecularButton
                size="sm"
                baseColor="#081412"
                lineColor="#5e8d77"
                textColor="#5e8d77"
                onClick={() => {
                  setShowCvDropdown(false);
                  cvInputRef.current?.click();
                }}
                className="w-full !py-2 font-mono text-xs font-bold rounded-xl flex items-center justify-center gap-1.5 mt-1 border border-emerald-500/30 hover:border-emerald-500 cursor-pointer"
              >
                <Plus size={14} /> ADD MORE CVS
              </SpecularButton>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
