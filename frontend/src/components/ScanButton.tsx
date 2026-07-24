type ScanButtonProps = {
  loading: boolean;
  onClick: () => void;
};

function ScanButton({ loading, onClick }: ScanButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-70"
    >
      <span aria-hidden="true">{loading ? "◌" : "↻"}</span>
      {loading ? "Scanning market..." : "Run scan"}
    </button>
  );
}

export default ScanButton;
