import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 min for search operations
});

// Datasets
export const getDatasets = () => api.get('/datasets').then(r => r.data);
export const createDataset = (name: string) => api.post('/datasets', { name }).then(r => r.data);
export const deleteDataset = (id: string) => api.delete(`/datasets/${id}`).then(r => r.data);

// Documents
export const uploadDocuments = (datasetId: string, files: File[]) => {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  return api.post(`/datasets/${datasetId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const listDocuments = (datasetId: string) => api.get(`/datasets/${datasetId}/documents`).then(r => r.data);
export const deleteDocument = (datasetId: string, filename: string) =>
  api.delete(`/datasets/${datasetId}/documents/${filename}`).then(r => r.data);

// Indexing
export const startIndexing = (datasetId: string, entityTypes?: string[], mode?: string) =>
  api.post(`/datasets/${datasetId}/index`, { entity_types: entityTypes, entity_type_mode: mode || 'default' }).then(r => r.data);
export const discoverEntityTypes = (sampleText: string) =>
  api.post('/datasets/temp/discover-entity-types', { sample_text: sampleText }).then(r => r.data);

// Graph
export const getGraphData = (datasetId: string, types?: string[], limit?: number) =>
  api.get(`/datasets/${datasetId}/graph`, { params: { types: types?.join(','), limit: limit || 200 } }).then(r => r.data);
export const getGraphStats = (datasetId: string) => api.get(`/datasets/${datasetId}/graph/stats`).then(r => r.data);
export const searchEntities = (datasetId: string, query: string, limit = 20) =>
  api.get(`/datasets/${datasetId}/graph/search-entities`, { params: { q: query, limit } }).then(r => r.data);
export const getEntityNeighborhood = (datasetId: string, entity: string, depth = 3) =>
  api.get(`/datasets/${datasetId}/graph/neighborhood`, { params: { entity, depth } }).then(r => r.data);

// Data Browser
export const getEntities = (datasetId: string, page = 1, pageSize = 20) =>
  api.get(`/datasets/${datasetId}/entities`, { params: { page, page_size: pageSize } }).then(r => r.data);
export const getRelationships = (datasetId: string, page = 1, pageSize = 20) =>
  api.get(`/datasets/${datasetId}/relationships`, { params: { page, page_size: pageSize } }).then(r => r.data);
export const getCommunities = (datasetId: string) => api.get(`/datasets/${datasetId}/communities`).then(r => r.data);
export const getCommunityDetail = (datasetId: string, communityId: number) =>
  api.get(`/datasets/${datasetId}/communities/${communityId}`).then(r => r.data);

// Search
export const searchKnowledge = (datasetId: string, query: string, mode: string) =>
  api.post(`/datasets/${datasetId}/search`, { query, mode }).then(r => r.data);

export interface SearchStreamCallbacks {
  onStatus: (status: string, message: string) => void;
  onChunk: (text: string) => void;
  onDone: (data: { query: string; mode: string; answer: string }) => void;
  onError: (message: string) => void;
}

export const searchKnowledgeStream = (
  datasetId: string,
  query: string,
  mode: string,
  callbacks: SearchStreamCallbacks,
): AbortController => {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`/api/datasets/${datasetId}/search/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode }),
        signal: controller.signal,
      });

      if (!response.ok) {
        callbacks.onError(`HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError('无法读取响应流');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;

          let eventType = '';
          let eventData = '';

          for (const line of eventBlock.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            else if (line.startsWith('data: ')) eventData = line.slice(6);
          }

          if (!eventData) continue;

          try {
            const data = JSON.parse(eventData);
            switch (eventType) {
              case 'status':
                callbacks.onStatus(data.status, data.message);
                break;
              case 'chunk':
                callbacks.onChunk(data.text);
                break;
              case 'done':
                callbacks.onDone(data);
                break;
              case 'error':
                callbacks.onError(data.message);
                break;
            }
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      callbacks.onError('网络连接失败，请稍后重试');
    }
  })();

  return controller;
};

// Config
export const getConfigStatus = () => api.get('/config/status').then(r => r.data);
export const checkApi = () => api.post('/config/check-api').then(r => r.data);

export default api;
