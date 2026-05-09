interface OverlayButtonProps {
  visible: boolean;
  loaded: boolean;
  onClick: () => void;
}

export function OverlayButton({ visible, loaded, onClick }: OverlayButtonProps) {
  if (!visible) return null;

  return (
    <div
      id="overlayButton"
      style={{ pointerEvents: loaded ? 'auto' : 'none' }}
      onClick={onClick}
    >
      {loaded ? (
        <>
          <span style={{ fontSize: 28, position: 'relative', top: -100 }}>
            邀请你通电话
          </span>
          <span
            style={{
              fontSize: 20,
              color: '#aaaaaa',
              position: 'relative',
              top: -130,
            }}
          >
            你接不接
          </span>
          <img
            src="image/receive.svg"
            width="100"
            height="100"
            style={{ position: 'relative', bottom: -200 }}
            alt="接听"
          />
          <span style={{ fontSize: 23, position: 'relative', bottom: -190 }}>
            接听
          </span>
        </>
      ) : (
        <span className="loading">正在寻找老师</span>
      )}
    </div>
  );
}
