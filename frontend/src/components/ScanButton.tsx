type ScanButtonProps = {
  loading: boolean;
  onClick: () => void;
};

function ScanButton({ loading, onClick }: ScanButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "12px 20px",
        fontSize: "18px",
        marginBottom: "30px",
        cursor: "pointer",
      }}
    >
      {loading ? "Scanning..." : "Scan Market"}
    </button>
  );
}

export default ScanButton;
