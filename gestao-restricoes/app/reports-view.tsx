'use client';
import { useMemo, useState } from 'react';
import {
  Archive,
  FileDown,
  FileSpreadsheet,
  Mail,
  MessageSquare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiBlob } from '@/lib/api';
export type ReportRow = {
  id: string;
  area?: string;
  cwp?: string;
  discipline?: string;
  task?: string;
  restriction?: string;
  category?: string;
  action?: string;
  owner?: string;
  company?: string;
  raisedAt?: string;
  dueAt?: string;
  status?: string;
  priority?: string;
  impact?: string;
};
const DONE = ['Concluída', 'Cancelada'],
  rank: Record<string, number> = { Crítica: 0, Alta: 1, Média: 2, Baixa: 3 };
const delta = (r: ReportRow, ref: string) =>
  r.dueAt
    ? Math.round(
        (new Date(r.dueAt + 'T12:00:00').getTime() -
          new Date(ref + 'T12:00:00').getTime()) /
          86400000,
      )
    : 99999;
const aging = (r: ReportRow, ref: string) =>
  r.raisedAt && r.status !== 'Concluída'
    ? Math.max(
        0,
        Math.floor(
          (new Date(ref).getTime() - new Date(r.raisedAt).getTime()) / 86400000,
        ),
      )
    : 0;
function criticality(r: ReportRow, ref: string) {
  if (DONE.includes(r.status || '')) return 'Baixa';
  const d = delta(r, ref);
  let s =
    d < 0 ? 40 : d === 0 ? 35 : d <= 2 ? 30 : d <= 5 ? 20 : d <= 10 ? 10 : 0;
  s += r.priority === 'Alta' ? 30 : r.priority === 'Média' ? 15 : 5;
  const a = aging(r, ref);
  s += a > 20 ? 20 : a >= 10 ? 15 : a >= 5 ? 10 : 0;
  if (
    /imped|paralisa|caminho crítico|atraso|impossibilidade|não iniciar|bloqueio/i.test(
      r.impact || '',
    )
  )
    s += 15;
  return s >= 70 ? 'Crítica' : s >= 50 ? 'Alta' : s >= 25 ? 'Média' : 'Baixa';
}
function situation(r: ReportRow, ref: string) {
  if (r.status === 'Concluída') return 'CONCLUÍDA';
  const d = delta(r, ref);
  if (d === 99999) return 'SEM PRAZO';
  if (d < 0) return `VENCIDA HÁ ${-d} DIA${d === -1 ? '' : 'S'}`;
  if (d === 0) return 'VENCE HOJE';
  if (d === 1) return 'VENCE AMANHÃ';
  if (d <= 7) return `VENCE EM ${d} DIAS`;
  return `PRAZO: ${new Date(r.dueAt! + 'T12:00:00').toLocaleDateString('pt-BR')}`;
}
const unique = (rows: ReportRow[], key: keyof ReportRow) => {
  const values = new Map<string, string>();
  for (const r of rows) {
    const value = String(r[key] || '').trim();
    if (value && !values.has(value.toLocaleLowerCase('pt-BR')))
      values.set(value.toLocaleLowerCase('pt-BR'), value);
  }
  return [...values.values()].sort((a, b) => a.localeCompare(b, 'pt-BR'));
};
function save(blob: Blob, disposition: string, fallback: string) {
  const m = disposition.match(/filename="?([^";]+)"?/);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = m?.[1] || fallback;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export default function ReportsView({
  rows,
  notify,
}: {
  rows: ReportRow[];
  notify: (
    text: string,
    kind?: 'success' | 'error' | 'info' | 'warning',
  ) => void;
}) {
  const params =
      typeof location === 'undefined'
        ? new URLSearchParams()
        : new URLSearchParams(location.search),
    today = new Date().toISOString().slice(0, 10);
  const [mode, setMode] = useState<'owner' | 'general'>('owner'),
    [owners, setOwners] = useState<string[]>(() =>
      params.get('responsavel') ? [params.get('responsavel')!] : [],
    ),
    [ref, setRef] = useState(today),
    [quick, setQuick] = useState('Todas as Pendências'),
    [impact, setImpact] = useState(false),
    [responseMode, setResponseMode] = useState(false),
    [busy, setBusy] = useState(''),
    [filters, setFilters] = useState<Record<string, string>>({
      company: params.get('empresa') || '',
      area: params.get('area') || '',
      cwp: '',
      discipline: '',
      category: '',
      status: '',
      priority: '',
      criticality: '',
    });
  const data = useMemo(
    () =>
      rows
        .filter((r) => {
          if (
            mode === 'owner' &&
            owners.length &&
            !owners.some(
              (x) =>
                x.localeCompare(r.owner || '', 'pt-BR', {
                  sensitivity: 'base',
                }) === 0,
            )
          )
            return false;
          for (const [k, v] of Object.entries(filters))
            if (
              v &&
              (k === 'criticality'
                ? criticality(r, ref)
                : String(r[k as keyof ReportRow] || '')) !== v
            )
              return false;
          const d = delta(r, ref),
            c = criticality(r, ref);
          return quick === 'Todas as Pendências'
            ? !DONE.includes(r.status || '')
            : quick === 'Somente Vencidas'
              ? d < 0 && !DONE.includes(r.status || '')
              : quick === 'Críticas'
                ? c === 'Crítica'
                : quick === 'Alta Prioridade'
                  ? r.priority === 'Alta'
                  : quick === 'Vencidas + Próximos 7 dias'
                    ? d <= 7 && !DONE.includes(r.status || '')
                    : quick === 'Em Tratamento'
                      ? r.status === 'Em Tratamento'
                      : quick === 'Próximos 3 dias'
                        ? d <= 3 && !DONE.includes(r.status || '')
                        : true;
        })
        .sort(
          (a, b) =>
            (delta(a, ref) < 0 ? 0 : 1) - (delta(b, ref) < 0 ? 0 : 1) ||
            rank[criticality(a, ref)] - rank[criticality(b, ref)] ||
            (a.priority === 'Alta' ? 0 : 1) - (b.priority === 'Alta' ? 0 : 1) ||
            delta(a, ref) - delta(b, ref) ||
            aging(b, ref) - aging(a, ref),
        ),
    [rows, owners, ref, quick, filters, mode],
  );
  const stats = {
    total: data.length,
    over: data.filter(
      (r) => delta(r, ref) < 0 && !DONE.includes(r.status || ''),
    ).length,
    critical: data.filter((r) => criticality(r, ref) === 'Crítica').length,
    high: data.filter((r) => r.priority === 'Alta').length,
    soon: data.filter(
      (r) =>
        delta(r, ref) >= 0 &&
        delta(r, ref) <= 7 &&
        !DONE.includes(r.status || ''),
    ).length,
  };
  const who = owners.length
    ? owners.join(', ')
    : mode === 'general'
      ? 'todos os responsáveis'
      : 'responsável selecionado';
  const payload = {
    owners,
    referenceDate: ref,
    quick,
    includeImpact: impact,
    responseMode,
    general: mode === 'general',
    ...filters,
  };
  const generate = async (batch = false) => {
    setBusy(batch ? 'batch' : 'pdf');
    try {
      const r = await apiBlob(
        batch ? '/reports/batch' : '/reports/pdf',
        payload,
      );
      save(
        r.blob,
        r.disposition,
        batch ? `Relatorios_${ref}.zip` : `Restricoes_${ref}.pdf`,
      );
      notify(
        batch
          ? 'Relatórios individuais gerados em ZIP.'
          : 'Relatório PDF gerado com sucesso.',
      );
    } catch (e) {
      notify(
        e instanceof Error ? e.message : 'Falha ao gerar relatório.',
        'error',
      );
    } finally {
      setBusy('');
    }
  };
  const generateExcel = async (batch = false) => {
    setBusy(batch ? 'excel-batch' : 'excel');
    try {
      const r = await apiBlob(
        batch ? '/reports/excel/batch' : '/reports/excel',
        payload,
      );
      save(
        r.blob,
        r.disposition,
        batch ? `Relatorios_Excel_${ref}.zip` : `Restricoes_${ref}.xlsx`,
      );
      notify(
        batch
          ? 'Relatórios Excel gerados em ZIP.'
          : 'Relatório Excel gerado com sucesso.',
      );
    } catch (e) {
      notify(
        e instanceof Error ? e.message : 'Falha ao gerar relatório Excel.',
        'error',
      );
    } finally {
      setBusy('');
    }
  };
  const date = new Date(ref + 'T12:00:00').toLocaleDateString('pt-BR'),
    email = `Assunto: Acompanhamento de Restrições - ${who} - ${date}\n\nPrezado(a) ${who},\n\nEncaminhamos o acompanhamento atualizado das restrições sob sua responsabilidade, conforme posição de ${date}.\n\nAtualmente constam ${stats.total} pendências, sendo ${stats.over} vencidas, ${stats.critical} críticas e ${stats.soon} com vencimento nos próximos 7 dias. Solicitamos especial atenção aos itens sinalizados como críticos e/ou vencidos, bem como atualização das respectivas ações e previsões de liberação.\n\nO detalhamento encontra-se no relatório anexo.\n\nAtenciosamente,\nPlanejamento`,
    short = `Bom dia, ${who}. Conforme acompanhamento atualizado, constam ${stats.total} restrições sob sua responsabilidade, sendo ${stats.over} vencidas e ${stats.critical} críticas. Favor verificar prioritariamente os itens sinalizados e atualizar as previsões de liberação.`;
  const copy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    notify(`${label} copiado.`);
  };
  const choices = {
    company: 'Empresa',
    area: 'Área / CWA',
    cwp: 'CWP',
    discipline: 'Disciplina',
    category: 'Categoria',
    status: 'Status',
    priority: 'Prioridade',
  };
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Mode
          active={mode === 'owner'}
          onClick={() => setMode('owner')}
          title="Relatório por Responsável"
          text="Pendências individuais para acompanhamento."
        />
        <Mode
          active={mode === 'general'}
          onClick={() => setMode('general')}
          title="Relatório Geral de Restrições"
          text="Posição consolidada para reunião gerencial."
        />
      </div>
      <section className="rounded-xl border bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {mode === 'owner' && (
            <label className="text-xs font-semibold md:col-span-2">
              Responsável (Ctrl para múltiplos)
              <select
                multiple
                value={owners}
                onChange={(e) =>
                  setOwners(
                    [...e.currentTarget.selectedOptions].map((o) => o.value),
                  )
                }
                className="mt-1 block h-24 w-full rounded-lg border p-2 font-normal"
              >
                {unique(rows, 'owner').map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          )}
          <label className="text-xs font-semibold">
            Data de referência
            <input
              type="date"
              value={ref}
              onChange={(e) => setRef(e.target.value)}
              className="mt-1 block h-10 w-full rounded-lg border px-3 font-normal"
            />
          </label>
          {Object.entries(choices).map(([k, l]) => (
            <label key={k} className="text-xs font-semibold">
              {l}
              <select
                value={filters[k]}
                onChange={(e) =>
                  setFilters({ ...filters, [k]: e.target.value })
                }
                className="mt-1 block h-10 w-full rounded-lg border px-2 font-normal"
              >
                <option value="">Todos</option>
                {unique(rows, k as keyof ReportRow).map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          ))}
          <label className="text-xs font-semibold">
            Criticidade
            <select
              value={filters.criticality}
              onChange={(e) =>
                setFilters({ ...filters, criticality: e.target.value })
              }
              className="mt-1 block h-10 w-full rounded-lg border px-2 font-normal"
            >
              <option value="">Todos</option>
              {['Crítica', 'Alta', 'Média', 'Baixa'].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            'Todas as Pendências',
            'Somente Vencidas',
            'Críticas',
            'Alta Prioridade',
            'Vencidas + Próximos 7 dias',
            'Próximos 3 dias',
            'Em Tratamento',
          ].map((x) => (
            <button
              key={x}
              onClick={() => setQuick(x)}
              className={`rounded-full border px-3 py-1.5 text-xs ${quick === x ? 'bg-[#2f6d5f] text-white' : 'bg-white'}`}
            >
              {x}
            </button>
          ))}
        </div>
        <label className="mt-4 flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={impact}
            onChange={(e) => setImpact(e.target.checked)}
          />
          Incluir Impacto / Observação
        </label>
        <label className="mt-3 flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={responseMode}
            onChange={(e) => setResponseMode(e.target.checked)}
          />
          Relatório para atualização pelo responsável (Nova Previsão e
          Comentário editáveis)
        </label>
      </section>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ['Total de pendências', stats.total],
          ['Vencidas', stats.over],
          ['Críticas', stats.critical],
          ['Alta prioridade', stats.high],
          ['Próximos 7 dias', stats.soon],
        ].map(([l, v]) => (
          <div key={String(l)} className="rounded-xl border bg-white p-4">
            <p className="text-xs text-slate-500">{l}</p>
            <b className="text-2xl">{v}</b>
          </div>
        ))}
      </div>
      <section className="rounded-xl border bg-white p-5">
        <h2 className="font-semibold">Resumo executivo</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Na data de emissão deste relatório, constam {stats.total} restrições
          sob responsabilidade de {who}, sendo {stats.over} vencidas,{' '}
          {stats.critical} classificadas como críticas e {stats.soon} com
          vencimento nos próximos 7 dias. Recomenda-se priorizar os itens
          destacados de acordo com prazo e impacto nas atividades.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            onClick={() => generate()}
            disabled={!!busy || (!owners.length && mode === 'owner')}
            className="bg-[#2f6d5f]"
          >
            <FileDown />
            {busy === 'pdf' ? 'Gerando...' : 'Gerar PDF'}
          </Button>
          <Button
            onClick={() => generateExcel()}
            disabled={!!busy || (!owners.length && mode === 'owner')}
            className="bg-[#ff5a14] hover:bg-[#e64e0c]"
          >
            <FileSpreadsheet />
            {busy === 'excel' ? 'Gerando...' : 'Gerar Excel'}
          </Button>
          <Button
            onClick={() => generateExcel(true)}
            disabled={!!busy}
            variant="outline"
          >
            <Archive />
            {busy === 'excel-batch' ? 'Gerando...' : 'Excel para todos (.ZIP)'}
          </Button>
          <Button
            onClick={() => generate(true)}
            disabled={!!busy}
            variant="outline"
          >
            <Archive />
            {busy === 'batch' ? 'Gerando...' : 'Baixar todos (.ZIP)'}
          </Button>
          <Button
            onClick={() => copy(email, 'Texto para e-mail')}
            variant="outline"
          >
            <Mail />
            Copiar texto para e-mail
          </Button>
          <Button
            onClick={() => copy(short, 'Mensagem resumida')}
            variant="outline"
          >
            <MessageSquare />
            Copiar mensagem
          </Button>
        </div>
      </section>
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="min-w-[1100px] w-full text-xs">
          <thead className="bg-[#173c33] text-white">
            <tr>
              {[
                'ID',
                'Área/CWA',
                'Disciplina',
                'Tarefa',
                'Restrição',
                'Ação para Liberação',
                'Prazo',
                'Situação',
                'Prioridade',
              ].map((x) => (
                <th key={x} className="px-3 py-3 text-left">
                  {x}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r) => {
              const d = delta(r, ref);
              return (
                <tr
                  key={r.id}
                  className={`border-t ${d < 0 ? 'bg-red-50' : d <= 1 ? 'bg-orange-50' : d <= 7 ? 'bg-amber-50' : r.status === 'Concluída' ? 'bg-emerald-50' : ''}`}
                >
                  <td className="px-3 py-3 font-bold">{r.id}</td>
                  <td>{r.area || '—'}</td>
                  <td>{r.discipline || '—'}</td>
                  <td className="max-w-[260px] px-3">{r.task || '—'}</td>
                  <td className="max-w-[280px] px-3">{r.restriction}</td>
                  <td className="max-w-[300px] px-3 font-medium text-[#173c33]">
                    {r.action || '—'}
                  </td>
                  <td className="whitespace-nowrap px-3">
                    {r.dueAt
                      ? new Date(r.dueAt + 'T12:00:00').toLocaleDateString(
                          'pt-BR',
                        )
                      : '—'}
                  </td>
                  <td className="whitespace-nowrap px-3 font-semibold">
                    {situation(r, ref)}
                  </td>
                  <td className="px-3">{r.priority || '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!data.length && (
          <p className="p-8 text-center text-sm text-slate-500">
            Nenhuma restrição corresponde aos filtros.
          </p>
        )}
      </div>
    </div>
  );
}
function Mode({
  active,
  onClick,
  title,
  text,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  text: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-4 text-left ${active ? 'border-[#2f6d5f] bg-[#edf4f1]' : 'bg-white'}`}
    >
      <Archive className="mb-2 text-[#2f6d5f]" />
      <b>{title}</b>
      <p className="text-xs text-slate-500">{text}</p>
    </button>
  );
}
