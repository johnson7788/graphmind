import { create } from 'zustand';
import { getDatasets } from '../services/api';

interface Dataset {
  id: string;
  name: string;
  created: string;
  has_index: boolean;
  index_complete: boolean;
  entity_count: number;
  relationship_count: number;
  community_count: number;
}

interface DatasetStore {
  datasets: Dataset[];
  selectedId: string | null;
  loading: boolean;
  fetchDatasets: () => Promise<void>;
  selectDataset: (id: string | null) => void;
}

export const useDatasetStore = create<DatasetStore>((set) => ({
  datasets: [],
  selectedId: null,
  loading: false,
  fetchDatasets: async () => {
    set({ loading: true });
    try {
      const data = await getDatasets();
      set({ datasets: data.datasets, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  selectDataset: (id) => set({ selectedId: id }),
}));
