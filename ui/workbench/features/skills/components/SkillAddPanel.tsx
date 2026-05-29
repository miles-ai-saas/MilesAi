"use client";

export function SkillAddPanel({
  onCreateBlank,
  onImportLocal,
  onImportZip,
  onImportGit,
}: {
  onCreateBlank: () => void;
  onImportLocal: () => void;
  onImportZip: () => void;
  onImportGit: () => void;
}) {
  return (
    <div className="resource-card border border-dashed border-line-soft bg-surface-elevated/50 p-5">
      <p className="mb-3 text-sm font-medium text-ink">添加技能包</p>
      <ul className="space-y-2 text-sm text-brand">
        <li>
          <button type="button" className="hover:underline" onClick={onCreateBlank}>
            创建空白技能包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportLocal}>
            装载本地技能包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportZip}>
            导入技能压缩包
          </button>
        </li>
        <li>
          <button type="button" className="hover:underline" onClick={onImportGit}>
            下载 Git 技能包
          </button>
        </li>
      </ul>
    </div>
  );
}
