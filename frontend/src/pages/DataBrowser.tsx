import { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Select,
  Tabs,
  Table,
  Tag,
  Empty,
  Divider,
  Tooltip,
  message,
} from 'antd';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { TeamOutlined, LinkOutlined } from '@ant-design/icons';
import { useDatasetStore } from '../stores/datasetStore';
import { getEntities, getRelationships } from '../services/api';

const { Title, Text } = Typography;

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

// ── Entity type ──────────────────────────────────────────────────────────
interface Entity {
  title: string;
  type: string;
  description: string;
}

// ── Relationship type ────────────────────────────────────────────────────
interface Relationship {
  source: string;
  target: string;
  description: string;
  weight: number;
}

// ── Entity columns ───────────────────────────────────────────────────────
const entityColumns: ColumnsType<Entity> = [
  {
    title: '名称',
    dataIndex: 'title',
    key: 'title',
    width: 220,
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
    title: '源',
    dataIndex: 'source',
    key: 'source',
    width: 160,
    ellipsis: true,
    render: (s: string) => <Text strong>{s}</Text>,
  },
  {
    title: '目标',
    dataIndex: 'target',
    key: 'target',
    width: 160,
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
    width: 90,
    align: 'center',
    render: (w: number) => <Tag color="orange">{w?.toFixed(1)}</Tag>,
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

  // ── Load data on dataset change ────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) {
      setEntities([]);
      setRelationships([]);
      return;
    }
    fetchEntities(1, entityPageSize);
    fetchRelationships(1, relPageSize);
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
          rowKey="title"
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
          rowKey={(r) => `${r.source}->${r.target}`}
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
            实体: {selectedDataset.entity_count} | 关系: {selectedDataset.relationship_count}
          </Text>
        )}
      </div>

      {/* Data Tabs */}
      <Tabs items={tabItems} defaultActiveKey="entities" />
    </div>
  );
}
