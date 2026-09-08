import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Mail, Calendar, Search, Loader2 } from "lucide-react";

interface EmailImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: (files: File[]) => void;
}

export default function EmailImportModal({ isOpen, onClose, onImportComplete }: EmailImportModalProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [sinceDate, setSinceDate] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("resume");
  const [isScanning, setIsScanning] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [scanResult, setScanResult] = useState<{ total_found: number, files: any[] } | null>(null);
  const [importSuccess, setImportSuccess] = useState<{ count: number } | null>(null);

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setIsScanning(true);
    
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"}/emails/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
        body: JSON.stringify({
          email_address: email,
          app_password: password,
          since_date: sinceDate,
          subject_filter: subjectFilter
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to scan emails");
      }

      const data = await response.json();
      setScanResult(data);
    } catch (error: any) {
      setErrorMsg(error.message);
    } finally {
      setIsScanning(false);
    }
  };

  const handleDownload = async () => {
    if (!scanResult || scanResult.files.length === 0) return;
    
    setIsScanning(true);
    setErrorMsg("");
    try {
      const downloadedFiles: File[] = [];
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      
      for (const fileMeta of scanResult.files) {
        const res = await fetch(`${API_URL}/emails/download/${fileMeta.file_id}`, {
            headers: { "ngrok-skip-browser-warning": "true" }
        });
        if (!res.ok) continue;
        
        const blob = await res.blob();
        const file = new File([blob], fileMeta.filename, { type: blob.type });
        downloadedFiles.push(file);
      }
      
      onImportComplete(downloadedFiles);
      setImportSuccess({ count: downloadedFiles.length });
    } catch (error: any) {
      setErrorMsg("Failed to download some attachments");
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative w-full max-w-md bg-[#0D1117] border border-[#232B36] rounded-xl shadow-2xl p-6"
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-gray-400 hover:text-white transition"
            >
              <X size={20} />
            </button>
            
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <Mail className="w-6 h-6 text-emerald-400" />
              </div>
              <h2 className="text-xl font-medium text-white tracking-wide">Import from Gmail</h2>
            </div>
            
            {importSuccess ? (
              <div className="text-center py-6">
                <div className="text-4xl font-light text-emerald-400 mb-2">{importSuccess.count}</div>
                <div className="text-gray-400 mb-8">CVs successfully imported to ATS</div>
                <button onClick={() => { setScanResult(null); setImportSuccess(null); }}
                        className="w-full bg-[#1A1F26] hover:bg-[#2E3743] border border-[#2E3743] text-white font-medium rounded-lg py-2 transition flex items-center justify-center gap-2">
                  Scan Again
                </button>
              </div>
            ) : !scanResult ? (
              <form onSubmit={handleScan} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Gmail Address</label>
                  <input required type="email" value={email} onChange={e => setEmail(e.target.value)}
                         className="w-full bg-[#1A1F26] border border-[#2E3743] rounded-lg px-4 py-2 text-white outline-none focus:border-emerald-500/50" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">App Password (16 chars)</label>
                  <input required type="password" value={password} onChange={e => setPassword(e.target.value)}
                         className="w-full bg-[#1A1F26] border border-[#2E3743] rounded-lg px-4 py-2 text-white outline-none focus:border-emerald-500/50" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Scan from Date (YYYY-MM-DD)</label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                    <input required type="date" value={sinceDate} onChange={e => setSinceDate(e.target.value)}
                           className="w-full bg-[#1A1F26] border border-[#2E3743] rounded-lg pl-10 pr-4 py-2 text-white outline-none focus:border-emerald-500/50" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Subject Contains (Optional)</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                    <input type="text" value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)} placeholder="e.g. resume, application"
                           className="w-full bg-[#1A1F26] border border-[#2E3743] rounded-lg pl-10 pr-4 py-2 text-white outline-none focus:border-emerald-500/50" />
                  </div>
                </div>
                
                {errorMsg && <div className="text-red-400 text-sm">{errorMsg}</div>}
                
                <button type="submit" disabled={isScanning}
                        className="w-full bg-emerald-500 hover:bg-emerald-600 text-black font-medium rounded-lg py-2 mt-4 transition flex items-center justify-center gap-2">
                  {isScanning ? <><Loader2 className="w-5 h-5 animate-spin" /> Scanning...</> : "Scan Inbox"}
                </button>
              </form>
            ) : (
              <div className="text-center py-6">
                <div className="text-4xl font-light text-white mb-2">{scanResult.total_found}</div>
                <div className="text-gray-400 mb-8">Valid CV attachments found</div>
                <button onClick={handleDownload} disabled={isScanning || scanResult.total_found === 0}
                        className="w-full bg-emerald-500 hover:bg-emerald-600 text-black font-medium rounded-lg py-2 transition flex items-center justify-center gap-2">
                  {isScanning ? <><Loader2 className="w-5 h-5 animate-spin" /> Downloading...</> : "Import to ATS"}
                </button>
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
