

export const SolverStatusMarker = (props: any) => {
  const { cx, cy, payload } = props;
  if (payload.hasInaccurate) {
    return (
      <circle cx={cx} cy={cy} r={6} stroke="#ef4444" strokeWidth={2} fill="white" />
    );
  }
  return null;
};
