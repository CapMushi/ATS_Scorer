import React from "react";
import { User, FileSpreadsheet, Trash2, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import GlassIcons from "@/components/GlassIcons";
import SpecularButton from "@/components/SpecularButton";
import { exportReport } from "@/lib/api";

interface CandidateResultsTableProps {
  allCandidates: any[];
  filteredCandidates: any[];
  isProcessing: boolean;
  cvFiles: File[];
  yoe: number;
  setYoe: (yoe: number) => void;
  strictMode: boolean;
  setSelectedCandidate: (candidate: any) => void;
  onRemoveCandidate?: (candidate: any) => void;
  onRetryCandidate?: (candidate: any) => void;
}

export default function CandidateResultsTable({
  allCandidates,
  filteredCandidates,
  isProcessing,
  cvFiles,
  yoe,
  setYoe,
  strictMode,
  setStrictMode,
  setSelectedCandidate,
  onRemoveCandidate,
  onRetryCandidate
}: CandidateResultsTableProps) {

  const handleDownloadCSV = async () => {
    if (!filteredCandidates || filteredCandidates.length === 0) return;

    try {
      await exportReport(filteredCandidates);
    } catch (err) {
      console.warn("Backend Excel export failed, generating local CSV report:", err);
      const headers = ["Rank", "Candidate Name", "Current Role", "Match Score (%)", "YOE", "Contact Email", "Contact Phone", "Matched Skills", "Missing Skills"];
      const rows = filteredCandidates.map((c, idx) => [
        idx + 1,
        `"${(c.candidate_name || c.contact?.name || "Candidate").replace(/"/g, '""')}"`,
        `"${(c.current_role || "N/A").replace(/"/g, '""')}"`,
        c.final_score_pct || 0,
        c.candidate_yoe || 0,
        `"${(c.contact?.email || "N/A").replace(/"/g, '""')}"`,
        `"${(c.contact?.phone || "N/A").replace(/"/g, '""')}"`,
        `"${(c.matched_skills || []).join(", ").replace(/"/g, '""')}"`,
        `"${(c.missing_skills || []).join(", ").replace(/"/g, '""')}"`,
      ]);

      const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ats_candidates_report_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      a.remove();
    }
  };

  if (allCandidates.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] w-full border border-dashed border-border rounded-2xl bg-black/20 text-muted-foreground">
        No candidates processed yet. Upload JD and CVs, then run analysis.
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="w-full flex flex-col gap-8"
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-2">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-3">
            Analysis Results
            <span className="text-xs bg-accent/20 text-accent px-3 py-1 rounded-full border border-accent/30 font-mono">
              {filteredCandidates.length} {filteredCandidates.length === 1 ? "Candidate" : "Candidates"} Qualified
            </span>
          </h2>
          {allCandidates.length !== filteredCandidates.length && (
            <p className="text-xs font-mono text-muted-foreground mt-1">
              Filtered out {allCandidates.length - filteredCandidates.length} candidates below {yoe} YOE{strictMode ? " or missing skills" : ""}.
            </p>
          )}
        </div>

        <SpecularButton
          onClick={handleDownloadCSV}
          disabled={filteredCandidates.length === 0}
          baseColor="#0b1716"
          lineColor="#5e8d77"
          textColor="#5e8d77"
          tint="#5e8d77"
          tintOpacity={0.25}
          radius={9999}
          size="sm"
          className="!px-5 !py-2.5 text-xs font-mono font-bold tracking-wider border border-[#5e8d77]/40 hover:border-[#5e8d77] hover:shadow-[0_0_20px_rgba(94,141,119,0.35)] active:scale-95 transition-all cursor-pointer flex items-center gap-2 disabled:opacity-40"
        >
          <FileSpreadsheet size={15} className="text-accent" />
          <span>EXPORT CSV REPORT</span>
        </SpecularButton>
      </div>

      <div className="overflow-x-auto overflow-y-auto max-h-[600px] relative rounded-3xl bg-secondary/10 border border-border shadow-xl backdrop-blur-sm">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 z-10 bg-[#0d1415]/95 backdrop-blur-md shadow-sm">
            <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-muted-foreground font-semibold">
              <th className="p-4 pl-6 w-16">Rank</th>
              <th className="p-4 w-48">Candidate</th>
              <th className="p-4 w-24">Match</th>
              <th className="p-4 w-24">YOE</th>
              <th className="p-4">Skills (Found / Missing)</th>
              <th className="p-4 pr-6 text-right w-32">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filteredCandidates.map((cand: any, idx: number) => {
              const isLowScore = cand.final_score_pct < 20;
              return (
                <tr key={idx} className={`hover:bg-white/5 transition-colors group ${!cand.llm_enhanced ? 'bg-green-900/20' : ''}`}>
                  <td className="p-4 pl-6 font-mono text-sm text-muted-foreground">#{idx + 1}</td>
                  <td className="p-4">
                    <div className="font-bold text-foreground text-sm truncate max-w-[200px] flex items-center gap-2" title={cand.candidate_name}>
                      {cand.candidate_name || "Unknown"}
                      {!cand.llm_enhanced && (
                        <span className="text-[9px] font-mono bg-green-500/20 text-green-400 border border-green-500/30 px-1.5 py-0.5 rounded-sm" title="Processed via Regex Fallback (LLM Not Used)">REGEX</span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate max-w-[200px]" title={cand.current_role}>{cand.current_role || "Candidate"}</div>
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 text-xs font-bold rounded-full border ${isLowScore ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-accent/20 text-accent border-accent/30'}`}>
                      {cand.final_score_pct?.toFixed(1)}%
                    </span>
                  </td>
                  <td className="p-4 text-sm font-mono text-muted-foreground">{cand.candidate_yoe}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-accent bg-accent/10 px-3 py-1 rounded-full border border-accent/20 whitespace-nowrap" title={cand.contextual_skills?.join(", ")}>
                        {cand.contextual_skills?.length || 0} Found
                      </span>
                      <span className="text-red-400 bg-red-500/10 px-3 py-1 rounded-full border border-red-500/20 whitespace-nowrap" title={cand.missing_skills?.join(", ")}>
                        {cand.missing_skills?.length || 0} Missing
                      </span>
                    </div>
                  </td>
                  <td className="p-4 pr-6 text-right flex justify-end">
                    <GlassIcons
                      colorful={true}
                      items={[
                        {
                          icon: <User size={18} strokeWidth={2.5} />,
                          color: 'indigo',
                          label: 'View Profile',
                          onClick: () => setSelectedCandidate(cand)
                        },
                        ...(!cand.llm_enhanced && onRetryCandidate ? [{
                          icon: <RefreshCw size={18} strokeWidth={2.5} />,
                          color: 'green',
                          label: 'Retry AI Analysis',
                          onClick: () => onRetryCandidate(cand)
                        }] : []),
                        ...(onRemoveCandidate ? [{
                          icon: <Trash2 size={18} strokeWidth={2.5} />,
                          color: 'red',
                          label: 'Remove Candidate',
                          onClick: () => onRemoveCandidate(cand)
                        }] : [])
                      ]}
                    />
                  </td>
                </tr>
              );
            })}

            {isProcessing && cvFiles.length > allCandidates.length && (
              Array.from({ length: Math.min(cvFiles.length - allCandidates.length, 5) }).map((_, sIdx) => (
                <tr key={`skel_${sIdx}`} className="animate-pulse bg-white/[0.01]">
                  <td className="p-4 pl-6 font-mono text-sm text-muted-foreground">
                    <div className="h-4 w-6 bg-white/10 rounded-full"></div>
                  </td>
                  <td className="p-4">
                    <div className="h-4 w-32 bg-white/10 rounded-lg mb-1.5 shadow-[0_0_10px_rgba(255,255,255,0.05)]"></div>
                    <div className="h-3 w-20 bg-white/5 rounded-lg"></div>
                  </td>
                  <td className="p-4">
                    <div className="h-6 w-14 bg-emerald-500/15 border border-emerald-500/20 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.1)]"></div>
                  </td>
                  <td className="p-4">
                    <div className="h-4 w-8 bg-white/10 rounded-full"></div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-20 bg-accent/15 rounded-full"></div>
                      <div className="h-6 w-20 bg-red-500/15 rounded-full"></div>
                    </div>
                  </td>
                  <td className="p-4 pr-6 text-right flex justify-end">
                    <div className="h-8 w-8 bg-white/10 rounded-full"></div>
                  </td>
                </tr>
              ))
            )}

            {!isProcessing && filteredCandidates.length === 0 && allCandidates.length > 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center bg-black/20">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <p className="text-sm font-bold text-amber-400 font-mono">No Candidates Qualified for Active Criteria</p>
                    <p className="text-xs text-muted-foreground font-mono max-w-md">
                      Filter criteria requires <span className="text-accent font-bold">&ge; {yoe} YOE</span>
                      {strictMode ? " and 100% must-have skill match." : "."}
                    </p>
                    <button
                      onClick={() => { setYoe(0); setStrictMode(false); }}
                      className="mt-2 text-xs text-accent hover:underline font-mono font-bold cursor-pointer"
                    >
                      Reset Filters to Show All ({allCandidates.length}) Candidates
                    </button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
