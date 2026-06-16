import { create } from 'zustand';

interface SearchResult {
  query: string;
  mode: string;
  answer: string;
  context?: string;
  time: string;
}

interface SearchStore {
  results: SearchResult[];
  currentResult: SearchResult | null;
  streaming: boolean;
  addResult: (result: SearchResult) => void;
  setCurrentResult: (result: SearchResult | null) => void;
  updateCurrentAnswer: (answer: string) => void;
  appendAnswerChunk: (chunk: string) => void;
  setStreaming: (streaming: boolean) => void;
  clearHistory: () => void;
}

export const useSearchStore = create<SearchStore>((set) => ({
  results: [],
  currentResult: null,
  streaming: false,
  addResult: (result) => set((state) => ({ results: [result, ...state.results] })),
  setCurrentResult: (result) => set({ currentResult: result }),
  updateCurrentAnswer: (answer) =>
    set((state) => ({
      currentResult: state.currentResult ? { ...state.currentResult, answer } : null,
    })),
  appendAnswerChunk: (chunk) =>
    set((state) => ({
      currentResult: state.currentResult
        ? { ...state.currentResult, answer: state.currentResult.answer + chunk }
        : null,
    })),
  setStreaming: (streaming) => set({ streaming }),
  clearHistory: () => set({ results: [], currentResult: null }),
}));
