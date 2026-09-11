import { useState, useRef, useEffect } from "react";
import localforage from "localforage";
import { analyzeSingleCandidate, convertDocxToPdf } from "@/lib/api";

interface UseCandidateAnalysisProps {
  jdFile: File | null;
  jdAnalysis: any;
  cvFiles: File[];
  yoe: number;
  skills: string[];
  lastProcessedSkills: string;
  setLastProcessedSkills: (skills: string) => void;
  allCandidates: any[];
  setAllCandidates: React.Dispatch<React.SetStateAction<any[]>>;
  fileUrls: Record<string, string>;
  setFileUrls: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setErrorMsg: (msg: string | null) => void;
}

export function useCandidateAnalysis({
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
}: UseCandidateAnalysisProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [convertedPdfUrls, setConvertedPdfUrls] = useState<Record<string, string>>({});
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // BACKGROUND DOCX CONVERSION (OPTIMISTIC PROCESSING)
  
  useEffect(() => {
    cvFiles.forEach(cvFile => {
      const isDocx = cvFile.name.toLowerCase().endsWith('.docx') || cvFile.name.toLowerCase().endsWith('.doc');
      if (isDocx && !convertedPdfUrls[cvFile.name]) {
        convertDocxToPdf(cvFile).then(pdfUrl => {
          setConvertedPdfUrls(prev => ({ ...prev, [cvFile.name]: pdfUrl }));
        }).catch(e => console.error(`Background conversion failed for ${cvFile.name}:`, e));
      }
    });
  }, [cvFiles, convertedPdfUrls]);

  const handleCancelAnalysis = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort("Cancelled by user");
      abortControllerRef.current = null;
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    setIsProcessing(false);
    setProgress(0);
    setErrorMsg("Batch analysis cancelled by user.");
  };

  const handleRunAnalysis = async () => {
    if (isProcessing) {
      handleCancelAnalysis();
      return;
    }

    setErrorMsg(null);
    if (!jdFile) {
      setErrorMsg("Please upload a Job Description first.");
      return;
    }
    if (!jdAnalysis || !jdAnalysis.jd_text) {
      setErrorMsg("JD is still parsing. Please wait.");
      return;
    }
    if (cvFiles.length === 0) {
      setErrorMsg("Please upload at least one CV.");
      return;
    }

    const currentSkillsStr = skills.join(",");
    const skillsChanged = lastProcessedSkills !== "" && lastProcessedSkills !== currentSkillsStr;
    
    let filesToProcess = cvFiles;

    if (skillsChanged) {
      // If skills changed, invalidate the cache and process ALL files again.
      setAllCandidates([]);
      localforage.removeItem('cached_candidates');
    } else {
      // Phase 5: Delta Processing (Only process new CVs)
      const existingFilenames = new Set(allCandidates.map((c: any) => c.file_name));
      filesToProcess = cvFiles.filter(f => !existingFilenames.has(f.name));
    }

    if (filesToProcess.length === 0) {
      setErrorMsg("All uploaded CVs have already been analyzed with the current skills.");
      return;
    }

    // Phase 6: Pagination Allowance (Max 10 per run to prevent 429 Too Many Requests)
    if (filesToProcess.length > 10) {
      filesToProcess = filesToProcess.slice(0, 10);
      setErrorMsg("Processing limited to 10 CVs per batch to prevent rate limits. Click 'Run Analysis' again when this batch finishes.");
    }

    // Save the snapshot of skills being used for this run
    setLastProcessedSkills(currentSkillsStr);
    localforage.setItem('cached_last_processed_skills', currentSkillsStr);

    setIsProcessing(true);
    setProgress(0);

    const urls: Record<string, string> = { ...fileUrls };
    filesToProcess.forEach(file => {
      urls[file.name] = URL.createObjectURL(file);
    });
    setFileUrls(urls);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const customSkillsStr = skills.join(",");
      let completedCount = 0;
      const totalCount = filesToProcess.length;
      
      const MAX_CONCURRENT = 1;
      const batches = [];
      
      // Chunk the files to process into batches of 12
      for (let i = 0; i < filesToProcess.length; i += MAX_CONCURRENT) {
        batches.push(filesToProcess.slice(i, i + MAX_CONCURRENT));
      }

      const results = [];
      
      for (const batch of batches) {
        if (controller.signal.aborted) break;

        const batchPromises = batch.map(async (cvFile) => {
          try {
            const result = await analyzeSingleCandidate(
              cvFile,
              jdAnalysis.jd_text,
              yoe,
              customSkillsStr,
              "",
              controller.signal
            );
            
              if (result) {
              results.push(result);
              // Stream UI update instantly as ONE finishes
              setAllCandidates(prev => {
                const newEmail = result.contact?.email?.toLowerCase().trim();
                const newPhone = result.contact?.phone?.replace(/\D/g, '');
                const newName = result.candidate_name?.toLowerCase().trim();

                const filtered = prev.filter(c => {
                  if (c.file_name === result.file_name) return false;
                  
                  const cEmail = c.contact?.email?.toLowerCase().trim();
                  const cPhone = c.contact?.phone?.replace(/\D/g, '');
                  const cName = c.candidate_name?.toLowerCase().trim();
                  
                  if (newEmail && cEmail && cEmail === newEmail) return false;
                  if (newPhone && cPhone && cPhone.length >= 7 && cPhone === newPhone) return false;
                  
                  // Deduplicate by exact name if filename/contact was slightly different or missing
                  if (newName && cName && cName === newName && newName !== "unknown") return false;
                  
                  return true;
                });

                const updated = [...filtered, result].sort((a, b) => b.final_score_pct - a.final_score_pct);
                localforage.setItem('cached_candidates', updated); // Persist to IndexedDB
                return updated;
              });
              completedCount++;
              setProgress(Math.floor((completedCount / totalCount) * 100));
            }
            return result;
          } catch (e: any) {
            if (e.name === 'AbortError' || e === 'Cancelled by user') {
              // Silently ignore aborts, they are expected when user cancels
            } else {
              console.error(`Failed to analyze ${cvFile.name}:`, e);
            }
            // Even on failure, update progress so it doesn't stall
            completedCount++;
            setProgress(Math.floor((completedCount / totalCount) * 100));
            return null; // Graceful skip on error
          }
        });

        // Wait for the current batch of 12 to complete before starting the next batch of 12
        await Promise.all(batchPromises);
      }

      setTimeout(() => {
        setIsProcessing(false);
      }, 1000);

    } catch (error: any) {
      if (error.name === "AbortError" || controller.signal.aborted) {
        console.log("Analysis aborted by user.");
        setErrorMsg("Batch analysis cancelled by user.");
      } else {
        console.error("Analysis failed:", error);
        setErrorMsg("Analysis failed. Please check the backend connection.");
      }
      setIsProcessing(false);
      setProgress(0);
    } finally {
      abortControllerRef.current = null;
    }
  };

  return {
    isProcessing,
    progress,
    convertedPdfUrls,
    handleRunAnalysis,
    handleCancelAnalysis
  };
}
