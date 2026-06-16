import { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Select,
  Tabs,
  Table,
  Tag,
  Empty,
  Divider,
  Modal,
  Descriptions,
  Spin,
  Progress,
  Tooltip,
  message,
  Card,
  Collapse,
} from 'antd';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import {
  TeamOutlined,
  LinkOutlined,
  ClusterOutlined,
  StarFilled,
  StarOutlined,
  ApartmentOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useDatasetStore } from '../stores/datasetStore';
import {
  getEntities,
  getRelationships,
  getCommunities,
  getCommunityDetail,
} from '../services/api';

const { Title, Text, Paragraph } = Typography;

// ── Color helpers ────────────────────────────────────────────────────────

const typeColorCache: Record<string, string> = {};
const palette = [
  'blue', 'green', 'orange', 'purple', 'cyan', 'magenta',
  'red', 'geekblue', 'volcano', 'gold', 'lime',
];
let colorIdx = 0;

function typeColor(type: string): string {
  if (!type) return 'default';
  if (!typeColorCache[type]) {
    typeColorCache[type] = palette[colorIdx % palette.length];
    colorIdx++;
  }
  return typeColorCache[type];
}

function weightColor(w: number): string {
  if (w >= 80) return '#52c41a';
  if (w >= 50) return '#1890ff';
  if (w >= 20) return '#faad14';
  return '#ff4d4f';
}

function ratingStars(rating: number): React.ReactNode {
  const full = Math.round(rating);
  return (
    <span>
      {Array.from({ length: 10 }, (_, i) =>
        i < full ? (
          <StarFilled key={i} style={{ color: '#fadb14', fontSize: 14, marginRight: 1 }} />
        ) : (
          <StarOutlined key={i} style={{ color: '#d9d9d9', fontSize: 14, marginRight: 1 }} />
        )
      )}
      <Text style={{ marginLeft: 6, fontWeight: 600 }}>{rating}/10</Text>
    </span>
  );
}

// ── Entity type ──────────────────────────────────────────────────────────
interface Entity {
  human_readable_id: number;
  title: string;
  type: string;
  description: string;
}

// ── Relationship type ────────────────────────────────────────────────────
interface Relationship {
  human_readable_id: number;
  source: string;
  target: string;
  description: string;
  weight: number;
}

// ── Community summary type ───────────────────────────────────────────────
interface Community {
  id: number;
  title: string;
  rating: number;
  [key: string]: unknown;
}

// ── Community detail type ────────────────────────────────────────────────
interface CommunityDetail {
  title: string;
  summary: string;
  full_content?: string;
  rank?: number;
  rating?: number;
  rating_explanation?: string;
  level?: number;
  parent?: number;
  children?: Record<string, unknown>;
  size?: number;
  period?: string;
  findings?: Array<{ summary: string; explanation: string }> | Record<string, unknown>;
  full_content_json?: {
    title?: string;
    summary?: string;
    findings?: Array<{ summary: string; explanation: string }>;
    rating?: number;
    rating_explanation?: string;
  };
  [key: string]: unknown;
}

/** Extract findings array from detail, handling both array and object formats. */
function getFindingsArray(
  detail: CommunityDetail,
): Array<{ summary: string; explanation: string }> | null {
  // Try full_content_json.findings first (always a proper array)
  const fcFindings = detail.full_content_json?.findings;
  if (Array.isArray(fcFindings) && fcFindings.length > 0) return fcFindings;
  // Try top-level findings
  if (Array.isArray(detail.findings) && detail.findings.length > 0) return detail.findings;
  return null;
}

/** Get the effective rating from rank or rating field. */
function getRating(detail: CommunityDetail): number | null {
  if (detail.rank != null) return detail.rank;
  if (detail.rating != null) return detail.rating;
  if (detail.full_content_json?.rating != null) return detail.full_content_json.rating;
  return null;
}

// ── Entity columns ───────────────────────────────────────────────────────
const entityColumns: ColumnsType<Entity> = [
  {
    title: 'ID',
    dataIndex: 'human_readable_id',
    key: 'id',
    width: 70,
    align: 'center',
  },
  {
    title: '名称',
    dataIndex: 'title',
    key: 'title',
    width: 200,
    ellipsis: true,
    render: (title: string) => <Text strong>{title}</Text>,
  },
  {
    title: '类型',
    dataIndex: 'type',
    key: 'type',
    width: 120,
    render: (type: string) => <Tag color={typeColor(type)}>{type || '未知'}</Tag>,
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    render: (desc: string) => (
      <Tooltip title={desc} placement="topLeft">
        <span>{desc}</span>
      </Tooltip>
    ),
  },
];

// ── Relationship columns ─────────────────────────────────────────────────
const relationshipColumns: ColumnsType<Relationship> = [
  {
    title: 'ID',
    dataIndex: 'human_readable_id',
    key: 'id',
    width: 70,
    align: 'center',
  },
  {
    title: '源',
    dataIndex: 'source',
    key: 'source',
    width: 150,
    ellipsis: true,
    render: (s: string) => <Text strong>{s}</Text>,
  },
  {
    title: '目标',
    dataIndex: 'target',
    key: 'target',
    width: 150,
    ellipsis: true,
    render: (t: string) => <Text strong>{t}</Text>,
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true,
    render: (desc: string) => (
      <Tooltip title={desc} placement="topLeft">
        <span>{desc}</span>
      </Tooltip>
    ),
  },
  {
    title: '权重',
    dataIndex: 'weight',
    key: 'weight',
    width: 130,
    render: (w: number) => (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Progress
          percent={w}
          size="small"
          showInfo={false}
          strokeColor={weightColor(w)}
          style={{ flex: 1, margin: 0 }}
        />
        <Text style={{ fontSize: 12, minWidth: 28, textAlign: 'right' }}>{w}</Text>
      </div>
    ),
  },
];

// ── Community columns (table only, no row click yet) ─────────────────────
const communityColumns: ColumnsType<Community> = [
  {
    title: 'ID',
    dataIndex: 'id',
    key: 'id',
    width: 80,
    align: 'center',
  },
  {
    title: '标题',
    dataIndex: 'title',
    key: 'title',
    ellipsis: true,
    render: (t: string) => <Text strong>{t}</Text>,
  },
  {
    title: '评分',
    dataIndex: 'rating',
    key: 'rating',
    width: 220,
    render: (r: number) => (r != null ? ratingStars(r) : <Text type="secondary">—</Text>),
  },
];

// ═══════════════════════════════════════════════════════════════════════
// ── Main Component ────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════
export default function DataBrowser() {
  const { datasets, selectedId, selectDataset, fetchDatasets } = useDatasetStore();

  // Entities state
  const [entities, setEntities] = useState<Entity[]>([]);
  const [entityTotal, setEntityTotal] = useState(0);
  const [entityPage, setEntityPage] = useState(1);
  const [entityPageSize, setEntityPageSize] = useState(20);
  const [entityLoading, setEntityLoading] = useState(false);

  // Relationships state
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [relTotal, setRelTotal] = useState(0);
  const [relPage, setRelPage] = useState(1);
  const [relPageSize, setRelPageSize] = useState(20);
  const [relLoading, setRelLoading] = useState(false);

  // Communities state
  const [communities, setCommunities] = useState<Community[]>([]);
  const [commLoading, setCommLoading] = useState(false);

  // Community detail modal
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<CommunityDetail | null>(null);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // ── Fetch entities ─────────────────────────────────────────────────────
  const fetchEntities = useCallback(
    async (page: number, pageSize: number) => {
      if (!selectedId) return;
      setEntityLoading(true);
      try {
        const data = await getEntities(selectedId, page, pageSize);
        setEntities(data.items as Entity[]);
        setEntityTotal(data.total);
        setEntityPage(data.page);
        setEntityPageSize(data.page_size);
      } catch {
        message.error('加载实体数据失败');
      } finally {
        setEntityLoading(false);
      }
    },
    [selectedId]
  );

  // ── Fetch relationships ────────────────────────────────────────────────
  const fetchRelationships = useCallback(
    async (page: number, pageSize: number) => {
      if (!selectedId) return;
      setRelLoading(true);
      try {
        const data = await getRelationships(selectedId, page, pageSize);
        setRelationships(data.items as Relationship[]);
        setRelTotal(data.total);
        setRelPage(data.page);
        setRelPageSize(data.page_size);
      } catch {
        message.error('加载关系数据失败');
      } finally {
        setRelLoading(false);
      }
    },
    [selectedId]
  );

  // ── Fetch communities ──────────────────────────────────────────────────
  const fetchCommunities = useCallback(async () => {
    if (!selectedId) return;
    setCommLoading(true);
    try {
      const data = await getCommunities(selectedId);
      setCommunities(data as Community[]);
    } catch {
      message.error('加载社区数据失败');
    } finally {
      setCommLoading(false);
    }
  }, [selectedId]);

  // ── Fetch community detail ─────────────────────────────────────────────
  const openCommunityDetail = async (communityId: number) => {
    if (!selectedId) return;
    setDetailOpen(true);
    setDetailLoading(true);
    setDetail(null);
    try {
      const data = await getCommunityDetail(selectedId, communityId);
      setDetail(data as CommunityDetail);
    } catch {
      message.error('加载社区详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Load data on dataset change ────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) {
      setEntities([]);
      setRelationships([]);
      setCommunities([]);
      return;
    }
    fetchEntities(1, entityPageSize);
    fetchRelationships(1, relPageSize);
    fetchCommunities();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // ── Table pagination handler ───────────────────────────────────────────
  const handleEntityTableChange = (pagination: TablePaginationConfig) => {
    fetchEntities(pagination.current ?? 1, pagination.pageSize ?? 20);
  };

  const handleRelTableChange = (pagination: TablePaginationConfig) => {
    fetchRelationships(pagination.current ?? 1, pagination.pageSize ?? 20);
  };

  const selectedDataset = datasets.find((d) => d.id === selectedId);

  // ── Tab items ──────────────────────────────────────────────────────────
  const tabItems = [
    {
      key: 'entities',
      label: (
        <span>
          <TeamOutlined /> 实体
          {selectedDataset && (
            <Tag style={{ marginLeft: 6 }}>{selectedDataset.entity_count}</Tag>
          )}
        </span>
      ),
      children: (
        <Table<Entity>
          rowKey="human_readable_id"
          columns={entityColumns}
          dataSource={entities}
          loading={entityLoading}
          pagination={{
            current: entityPage,
            pageSize: entityPageSize,
            total: entityTotal,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={handleEntityTableChange}
          size="middle"
          scroll={{ x: 800 }}
        />
      ),
    },
    {
      key: 'relationships',
      label: (
        <span>
          <LinkOutlined /> 关系
          {selectedDataset && (
            <Tag style={{ marginLeft: 6 }}>{selectedDataset.relationship_count}</Tag>
          )}
        </span>
      ),
      children: (
        <Table<Relationship>
          rowKey="human_readable_id"
          columns={relationshipColumns}
          dataSource={relationships}
          loading={relLoading}
          pagination={{
            current: relPage,
            pageSize: relPageSize,
            total: relTotal,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={handleRelTableChange}
          size="middle"
          scroll={{ x: 800 }}
        />
      ),
    },
    {
      key: 'communities',
      label: (
        <span>
          <ClusterOutlined /> 社区报告
          {selectedDataset && (
            <Tag style={{ marginLeft: 6 }}>{selectedDataset.community_count}</Tag>
          )}
        </span>
      ),
      children: (
        <Table<Community>
          rowKey="id"
          columns={communityColumns}
          dataSource={communities}
          loading={commLoading}
          pagination={{
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            showTotal: (total) => `共 ${total} 条`,
          }}
          size="middle"
          scroll={{ x: 600 }}
          onRow={(record) => ({
            onClick: () => openCommunityDetail(record.id),
            style: { cursor: 'pointer' },
          })}
        />
      ),
    },
  ];

  // ── No dataset selected state ──────────────────────────────────────────
  if (!selectedId) {
    return (
      <div>
        <Title level={4}>数据浏览</Title>
        <Divider />
        <div style={{ marginBottom: 24 }}>
          <Text strong style={{ marginRight: 12 }}>选择数据集：</Text>
          <Select
            placeholder="请选择数据集"
            style={{ width: 320 }}
            loading={useDatasetStore.getState().loading}
            onChange={(val) => selectDataset(val)}
            options={datasets.map((d) => ({
              label: `${d.name}${d.has_index ? '' : ' (未索引)'}`,
              value: d.id,
            }))}
          />
        </div>
        <Empty description="请先选择一个数据集以浏览数据" />
      </div>
    );
  }

  return (
    <div>
      <Title level={4}>数据浏览</Title>
      <Divider />

      {/* Dataset Selector */}
      <div style={{ marginBottom: 24 }}>
        <Text strong style={{ marginRight: 12 }}>当前数据集：</Text>
        <Select
          value={selectedId}
          style={{ width: 320 }}
          onChange={(val) => selectDataset(val)}
          options={datasets.map((d) => ({
            label: `${d.name}${d.has_index ? '' : ' (未索引)'}`,
            value: d.id,
          }))}
        />
        {selectedDataset && (
          <Text type="secondary" style={{ marginLeft: 12 }}>
            实体: {selectedDataset.entity_count} | 关系: {selectedDataset.relationship_count} | 社区: {selectedDataset.community_count}
          </Text>
        )}
      </div>

      {/* Data Tabs */}
      <Tabs items={tabItems} defaultActiveKey="entities" />

      {/* Community Detail Modal */}
      <Modal
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={960}
        title={detail?.title || '社区报告详情'}
        destroyOnHidden
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <Spin size="large" />
          </div>
        ) : detail ? (() => {
          const rating = getRating(detail);
          const findings = getFindingsArray(detail);
          const hasFullContent = detail.full_content && detail.full_content.length > 0;

          return (
            <div style={{ maxHeight: '75vh', overflowY: 'auto' }}>
              <Title level={5} style={{ marginBottom: 12 }}>{detail.title}</Title>

              {/* ── Metadata bar ─────────────────────────────────────── */}
              <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
                <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
                  {rating != null && (
                    <Descriptions.Item label="评分">
                      {ratingStars(rating)}
                    </Descriptions.Item>
                  )}
                  {detail.level != null && (
                    <Descriptions.Item label="层级">
                      <Tag color="blue">Level {detail.level}</Tag>
                    </Descriptions.Item>
                  )}
                  {detail.size != null && (
                    <Descriptions.Item label="规模">
                      <Tag>{detail.size} 个实体</Tag>
                    </Descriptions.Item>
                  )}
                  {detail.parent != null && (
                    <Descriptions.Item label="父社区">
                      <Tag color="purple">#{detail.parent}</Tag>
                    </Descriptions.Item>
                  )}
                  {detail.period && (
                    <Descriptions.Item label="周期">
                      {detail.period}
                    </Descriptions.Item>
                  )}
                  {detail.rating_explanation && (
                    <Descriptions.Item label="评分说明" span={3}>
                      <Text style={{ fontSize: 13 }}>{detail.rating_explanation}</Text>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </Card>

              {/* ── Summary ──────────────────────────────────────────── */}
              {detail.summary && (
                <Card
                  size="small"
                  title={<span><FileTextOutlined /> 摘要</span>}
                  style={{ marginBottom: 16 }}
                >
                  <Paragraph style={{ lineHeight: 1.8, marginBottom: 0 }}>
                    {detail.summary}
                  </Paragraph>
                </Card>
              )}

              {/* ── Full Report (markdown) ───────────────────────────── */}
              {hasFullContent && (
                <Card
                  size="small"
                  title={<span><ApartmentOutlined /> 完整报告</span>}
                  style={{ marginBottom: 16 }}
                >
                  <div
                    className="community-report-markdown"
                    style={{
                      lineHeight: 1.8,
                      fontSize: 14,
                      overflowX: 'hidden',
                    }}
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {detail.full_content!}
                    </ReactMarkdown>
                  </div>
                </Card>
              )}

              {/* ── Findings (if no full_content, show separately) ──── */}
              {!hasFullContent && findings && (
                <Card
                  size="small"
                  title={<span><ApartmentOutlined /> 发现 ({findings.length})</span>}
                  style={{ marginBottom: 16 }}
                >
                  <Collapse
                    ghost
                    items={findings.map((f, idx) => ({
                      key: idx,
                      label: (
                        <Text strong style={{ color: '#1890ff' }}>
                          {idx + 1}. {f.summary}
                        </Text>
                      ),
                      children: (
                        <Paragraph
                          type="secondary"
                          style={{ fontSize: 13, lineHeight: 1.7, marginBottom: 0 }}
                        >
                          {f.explanation}
                        </Paragraph>
                      ),
                    }))}
                    defaultActiveKey={[0]}
                  />
                </Card>
              )}
            </div>
          );
        })() : (
          <Empty description="无法加载社区详情" />
        )}
      </Modal>
    </div>
  );
}
