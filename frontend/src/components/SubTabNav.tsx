interface SubTab {
  id: string;
  label: string;
}

interface Props {
  tabs: SubTab[];
  active: string;
  onChange: (id: string) => void;
}

export default function SubTabNav({ tabs, active, onChange }: Props) {
  return (
    <div className="flex gap-1 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
            active === tab.id
              ? "bg-[rgba(96,165,250,0.1)] text-[#60a5fa] border border-[rgba(96,165,250,0.2)]"
              : "bg-transparent text-[#64748b] border border-transparent hover:text-[#94a3b8]"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
