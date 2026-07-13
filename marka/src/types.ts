export interface UserAccount {
  markaId: string;
  pin: string;
  credits: number;
  createdAt: string;
}

export interface BatchMarking {
  id: string;
  title: string;
  date: string;
  subject: string;
  totalPapers: number;
  processedCount: number;
  rejectedCount: number;
  creditsDeducted: number;
  questionsCount: number;
  optionsCount: number;
  answerKey: Record<number, string>;
  bonusEnabled: boolean;
  bonusMarks: number;
  negativeMarking: number;
}

export interface GradedPaper {
  id: string;
  batchId: string;
  filename: string;
  studentName: string;
  score: number;
  maxScore: number;
  correctCount: number;
  wrongCount: number;
  blankCount: number;
  percentage: number;
  confidence: number; // e.g. 0.98 for 98%
  gradedAt: string;
  studentAnswers: Record<number, string>;
  status: 'uploading' | 'queued' | 'complete' | 'rejected';
  errorMessage: string | null;
  imageUrl: string; // Base64 or stored URL representation
}

export interface DemoConfig {
  demoDownloadsCount: number;
  maxDemoDownloads: number;
}
