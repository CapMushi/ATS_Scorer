"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import CircularGallery from "@/components/CircularGallery";
import GamerProfileModal from "@/components/GamerProfileModal";
import CVPreviewModal from "@/components/CVPreviewModal";
import { parseJd } from "@/lib/api";
import localforage from "localforage";
import { cn } from "@/lib/utils";
import { NoiseTexture } from "@/registry/magicui/noise-texture";
import CosmicDust from "@/components/lightswind/cosmic-dust";
import UploadSection from "@/components/UploadSection";
import ActionControls from "@/components/ActionControls";
import EmailImportModal from "@/components/EmailImportModal";
import { Zap, Wand2 } from "lucide-react";

import BatchEngine from "@/components/BatchEngine";
import SkillsFilter from "@/components/SkillsFilter";
import CandidateResultsTable from "@/components/CandidateResultsTable";
import { useCandidateAnalysis } from "@/hooks/useCandidateAnalysis";

export default function Home() {
  const [allCandidates, setAllCandidates] = useState<any[]>([]);
  const [isFilterLoading, setIsFilterLoading] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<any>(null);
  const [showCV, setShowCV] = useState(false);
  const [yoe, setYoe] = useState(0);
  const [strictMode, setStrictMode] = useState(false);
  const [selectedUniversities, setSelectedUniversities] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [jdAnalysis, setJdAnalysis] = useState<any>(null);
  const [fileUrls, setFileUrls] = useState<Record<string, string>>({});
  const [skills, setSkills] = useState<string[]>([]);
  const [lastProcessedSkills, setLastProcessedSkills] = useState<string>("");
  const [isParsingJd, setIsParsingJd] = useState(false);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [cvFiles, setCvFiles] = useState<File[]>([]);
  const [showJdDropdown, setShowJdDropdown] = useState(false);
  const [showCvDropdown, setShowCvDropdown] = useState(false);
  const [isFastMode, setIsFastMode] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);

  const jdDropdownRef = useRef<HTMLDivElement>(null);
  const cvDropdownRef = useRef<HTMLDivElement>(null);

  // Derive filtered candidates reactively based on Min YOE and Strict Mode
  const filteredCandidates = useMemo(() => {
    if (!allCandidates || allCandidates.length === 0) return [];

    return allCandidates.filter((c: any) => {
      const meetsYoe = (c.candidate_yoe || 0) >= yoe;
      if (!meetsYoe) return false;

      if (strictMode) {
        const hasMissing = c.missing_skills && c.missing_skills.length > 0;
        if (hasMissing) return false;
      }

      if (selectedUniversities.length > 0) {
        const candidateUnis = c.normalized_universities || [];
        const hasSelectedUni = candidateUnis.some((uni: string) => selectedUniversities.includes(uni));
        if (!hasSelectedUni) return false;
      }

      return true;
    });
  }, [allCandidates, yoe, strictMode, selectedUniversities]);

  // Trigger smooth skeleton loading animation whenever Min YOE or Strict Mode changes
  useEffect(() => {
    if (allCandidates.length > 0) {
      setIsFilterLoading(true);
      const timer = setTimeout(() => {
        setIsFilterLoading(false);
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [yoe, strictMode, selectedUniversities]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (jdDropdownRef.current && !jdDropdownRef.current.contains(e.target as Node)) {
        setShowJdDropdown(false);
      }
      if (cvDropdownRef.current && !cvDropdownRef.current.contains(e.target as Node)) {
        setShowCvDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleAddCvFiles = (newFiles: FileList | File[]) => {
    const fileArray = Array.from(newFiles);
    setCvFiles(prev => {
      const existing = new Set(prev.map(f => `${f.name}_${f.size}`));
      const unique = fileArray.filter(f => !existing.has(`${f.name}_${f.size}`));
      const updated = [...prev, ...unique];
      localforage.setItem('cached_files', updated);
      return updated;
    });
  };

  const handleRemoveCvFile = (indexToRemove: number) => {
    setCvFiles(prev => {
      const fileToRemove = prev[indexToRemove];
      setAllCandidates(candidates => {
        const updated = candidates.filter((c: any) => c.file_name !== fileToRemove.name);
        localforage.setItem('cached_candidates', updated);
        return updated;
      });
      const updatedFiles = prev.filter((_, idx) => idx !== indexToRemove);
      localforage.setItem('cached_files', updatedFiles);
      return updatedFiles;
    });
  };

  const handleClearAllCvs = () => {
    setCvFiles([]);
    setAllCandidates([]);
    localforage.removeItem('cached_files');
    localforage.removeItem('cached_candidates');
    localforage.removeItem('cached_last_processed_skills');
    setLastProcessedSkills("");
    setShowCvDropdown(false);
  };

  const handleRemoveCandidateResult = (candidateToRemove: any) => {
    setAllCandidates(prev => {
      const updated = prev.filter(c => c.file_name !== candidateToRemove.file_name);
      localforage.setItem('cached_candidates', updated);
      return updated;
    });
    setCvFiles(prev => {
      const updated = prev.filter(f => f.name !== candidateToRemove.file_name);
      localforage.setItem('cached_files', updated);
      return updated;
    });
  };

  const handleRetryCandidate = (candidateToRetry: any) => {
    setAllCandidates(prev => {
      const updated = prev.filter(c => c.file_name !== candidateToRetry.file_name);
      localforage.setItem('cached_candidates', updated);
      return updated;
    });
    // Do NOT remove from cvFiles, so they get reprocessed next time Run Analysis is clicked
    setErrorMsg(`Queued ${candidateToRetry.candidate_name} for Retry. Click 'Run Analysis' to process them with AI.`);
  };

  const handleRemoveJdFile = () => {
    setJdFile(null);
    setJdAnalysis(null);
    setSkills([]);
    localforage.removeItem('cached_jd_file');
    localforage.removeItem('cached_jd_analysis');
    localforage.removeItem('cached_skills');
    setShowJdDropdown(false);
  };

  useEffect(() => {
    if (errorMsg) {
      const timer = setTimeout(() => {
        setErrorMsg(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [errorMsg]);

  // Phase 5: Privacy-First IndexedDB Cache Hydration
  useEffect(() => {
    const hydrate = async () => {
      try {
        const cachedCandidates = await localforage.getItem<any[]>('cached_candidates');
        const cachedFiles = await localforage.getItem<File[]>('cached_files');
        const cachedJdFile = await localforage.getItem<File>('cached_jd_file');
        const cachedJdAnalysis = await localforage.getItem<any>('cached_jd_analysis');
        const cachedSkills = await localforage.getItem<string[]>('cached_skills');
        const cachedLastSkills = await localforage.getItem<string>('cached_last_processed_skills');
        
        if (cachedJdFile) setJdFile(cachedJdFile);
        if (cachedJdAnalysis) setJdAnalysis(cachedJdAnalysis);
        if (cachedSkills && cachedSkills.length > 0) setSkills(cachedSkills);
        if (cachedLastSkills) setLastProcessedSkills(cachedLastSkills);
        
        if (cachedCandidates && cachedCandidates.length > 0) {
          setAllCandidates(cachedCandidates);
        }
        
        if (cachedFiles && cachedFiles.length > 0) {
          setCvFiles(cachedFiles);
          const urls: Record<string, string> = {};
          cachedFiles.forEach(f => {
            urls[f.name] = URL.createObjectURL(f);
          });
          setFileUrls(urls);
        }
        
        const cachedFastMode = await localforage.getItem<boolean>('cached_fast_mode');
        if (cachedFastMode !== null) setIsFastMode(cachedFastMode);
      } catch (e) {
        console.error("Failed to hydrate session cache", e);
      }
    };
    hydrate();
  }, []);

  const handleJdUpload = async (file: File) => {
    setJdFile(file);
    localforage.setItem('cached_jd_file', file);
    setErrorMsg(null);
    setIsParsingJd(true);
    try {
      const parsed = await parseJd(file);
      setJdAnalysis(parsed);
      setSkills(parsed.must_have_skills || []);
      localforage.setItem('cached_jd_analysis', parsed);
      localforage.setItem('cached_skills', parsed.must_have_skills || []);
    } catch (error) {
      console.error("Failed to parse JD:", error);
      setErrorMsg("Failed to auto-parse JD. Please check backend connection.");
    }
    setIsParsingJd(false);
  };

  // Sync manual skill changes to cache
  useEffect(() => {
    if (skills.length > 0) {
      localforage.setItem('cached_skills', skills);
    }
  }, [skills]);

  const {
    isProcessing,
    progress,
    convertedPdfUrls,
    handleRunAnalysis,
    handleCancelAnalysis
  } = useCandidateAnalysis({
    jdFile,
    jdAnalysis,
    cvFiles,
    yoe,
    skills,
    lastProcessedSkills,
    setLastProcessedSkills,
    allCandidates,
    setAllCandidates,
    fileUrls,
    setFileUrls,
    setErrorMsg
  });

  return (
    <main className="relative min-h-screen flex flex-col items-center p-8 lg:p-24 pb-32 overflow-hidden bg-background">
      {!isFastMode && (
        <>
          <CosmicDust
            className="fixed inset-0 pointer-events-none z-0"
            particleColors={["#5e8d77", "#34d399", "#10b981", "#6ee7b7", "#a7f3d0", "#ffffff"]}
            particleCount={80}
            speed={0.2}
            opacity={0.5}
            minSize={0.8}
            maxSize={2.2}
          />
          <NoiseTexture
            className={cn(
              "fixed inset-0 pointer-events-none z-0 opacity-45 mix-blend-overlay",
              "mask-[radial-gradient(circle_at_center,white_75%,transparent_100%)]"
            )}
          />
        </>
      )}

      <div className="relative z-10 w-full flex flex-col items-center">
        <div className="flex flex-col md:flex-row items-center justify-between w-full max-w-7xl mt-6 border-b border-white/10 pb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center font-black text-primary-foreground shadow-lg shadow-primary/20">
              AI
            </div>
            <h1 className="text-3xl font-black tracking-tighter bg-clip-text text-transparent bg-gradient-to-br from-white to-white/40">
              ATS<span className="text-primary">SCORER</span>
            </h1>
            
            <button
              onClick={() => {
                const newMode = !isFastMode;
                setIsFastMode(newMode);
                localforage.setItem('cached_fast_mode', newMode);
              }}
              className={cn(
                "ml-6 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-300 border backdrop-blur-md",
                isFastMode 
                  ? "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20 shadow-sm" 
                  : "bg-primary/10 border-primary/30 text-primary hover:bg-primary/20 shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]"
              )}
              title={isFastMode ? "Fast Mode Active (Animations Disabled)" : "Fancy Mode Active (Animations Enabled)"}
            >
              {isFastMode ? <Zap size={14} className="animate-pulse" /> : <Wand2 size={14} />}
              {isFastMode ? "FAST" : "FANCY"}
            </button>
          </div>

          <UploadSection
            jdFile={jdFile}
            cvFiles={cvFiles}
            isParsingJd={isParsingJd}
            showJdDropdown={showJdDropdown}
            setShowJdDropdown={setShowJdDropdown}
            showCvDropdown={showCvDropdown}
            setShowCvDropdown={setShowCvDropdown}
            handleJdUpload={handleJdUpload}
            handleAddCvFiles={handleAddCvFiles}
            handleRemoveJdFile={handleRemoveJdFile}
            handleRemoveCvFile={handleRemoveCvFile}
            handleClearAllCvs={handleClearAllCvs}
            onOpenEmailImport={() => setShowEmailModal(true)}
          />
        </div>

        <ActionControls
          yoe={yoe}
          setYoe={setYoe}
          strictMode={strictMode}
          setStrictMode={setStrictMode}
          selectedUniversities={selectedUniversities}
          setSelectedUniversities={setSelectedUniversities}
        />

        <div className="flex flex-col lg:flex-row items-start justify-center gap-12 w-full max-w-7xl mt-16">
          <div className="flex flex-col gap-8 w-full lg:w-[38.2%]">
            <BatchEngine
              isProcessing={isProcessing}
              progress={progress}
              errorMsg={errorMsg}
              handleRunAnalysis={handleRunAnalysis}
            />

            <SkillsFilter
              skills={skills}
              setSkills={setSkills}
              jdFile={jdFile}
            />
          </div>

          <div className="flex flex-col flex-grow w-full lg:w-[61.8%] min-h-[500px]">
            <CandidateResultsTable
              allCandidates={allCandidates}
              filteredCandidates={filteredCandidates}
              isProcessing={isProcessing}
              cvFiles={cvFiles}
              yoe={yoe}
              setYoe={setYoe}
              strictMode={strictMode}
              setStrictMode={setStrictMode}
              setSelectedCandidate={setSelectedCandidate}
              onRemoveCandidate={handleRemoveCandidateResult}
              onRetryCandidate={handleRetryCandidate}
            />
          </div>
        </div>

        {allCandidates.length > 0 && (
          <div className="w-full max-w-[1700px] z-10 mt-12 mb-20 px-0 lg:px-4">
            <h3 className="text-2xl font-bold mb-8 text-foreground flex items-center gap-3">
              <span className="w-2 h-8 bg-accent rounded-full shadow-[0_0_15px_rgba(94,141,119,0.5)]"></span>
              Visual Candidate Gallery
            </h3>
            {isFilterLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {[1, 2, 3, 4].map((n) => (
                  <div key={n} className="h-48 rounded-3xl bg-black/40 border border-white/10 p-5 flex flex-col justify-between animate-pulse">
                    <div className="flex justify-between items-center">
                      <div className="h-5 w-32 bg-white/10 rounded-md"></div>
                      <div className="h-6 w-14 bg-accent/20 rounded-full"></div>
                    </div>
                    <div className="space-y-3 mt-4">
                      <div className="h-4 w-48 bg-white/5 rounded-md"></div>
                      <div className="h-4 w-32 bg-white/5 rounded-md"></div>
                    </div>
                    <div className="h-10 w-full bg-white/10 rounded-xl mt-4"></div>
                  </div>
                ))}
              </div>
            ) : filteredCandidates.length > 0 ? (
              <CircularGallery
                items={filteredCandidates}
                onItemClick={(item) => {
                  setSelectedCandidate(item);
                  setShowCV(true);
                }}
              />
            ) : (
              <div className="p-8 text-center text-sm font-mono text-muted-foreground bg-black/20 rounded-3xl border border-white/5 w-full">
                No gallery cards available under current filters.
              </div>
            )}
          </div>
        )}

        {selectedCandidate && !showCV && (
          <GamerProfileModal
            candidate={selectedCandidate}
            onClose={() => {
              setSelectedCandidate(null);
              setShowCV(false);
            }}
            rank={allCandidates.indexOf(selectedCandidate) + 1}
          />
        )}

        {selectedCandidate && showCV && (
          <CVPreviewModal
            candidate={selectedCandidate}
            fileUrl={fileUrls[selectedCandidate.file_name]}
            preConvertedPdfUrl={convertedPdfUrls[selectedCandidate.file_name]}
            onClose={() => {
              setSelectedCandidate(null);
              setShowCV(false);
            }}
          />
        )}
        
        <EmailImportModal 
          isOpen={showEmailModal} 
          onClose={() => setShowEmailModal(false)}
          onImportComplete={(files) => {
             handleAddCvFiles(files);
          }}
        />
      </div>
    </main>
  );
}
