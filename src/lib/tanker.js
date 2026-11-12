// 제티에 댄 탱커 옆모습 (140×100). 팀 console 프로토타입(console/js/ui/board.js)의 그림을 그대로 옮겼다.
export function tankerSVG({ empty = false, hull = '#26364f' } = {}) {
  const sea = '<rect width="140" height="100" fill="#3a8edb"/><rect y="62" width="140" height="38" fill="#2f80cc"/>' +
    '<path d="M0 82 q7 -3 14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0" fill="none" stroke="#7cc0f2" stroke-width="1" opacity=".7"/>' +
    '<path d="M-7 92 q7 -3 14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0 t14 0" fill="none" stroke="#7cc0f2" stroke-width="1" opacity=".45"/>'
  const quay = '<rect width="140" height="16" fill="#c4cad2"/><rect y="15" width="140" height="2" fill="#8e96a1"/>' +
    '<rect x="56" y="5" width="30" height="10" fill="#8b929c"/><rect x="59" y="17" width="2.5" height="12" fill="#77808b"/><rect x="80" y="17" width="2.5" height="12" fill="#77808b"/>' +
    '<path d="M66 5 V0 M76 5 V0" stroke="#5f6670" stroke-width="1.6"/>'
  if (empty) {
    return `<svg viewBox="0 0 140 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${sea}${quay}
      <text x="70" y="66" text-anchor="middle" font-size="13" font-weight="700" fill="#dcecff" font-family="Noto Sans KR, sans-serif">공석</text></svg>`
  }
  return `<svg viewBox="0 0 140 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${sea}${quay}
    <path d="M8 44 H122 Q133 46 136 54 Q133 63 122 66 H17 Q10 62 8 54 Z" fill="${hull}"/>
    <path d="M10 60 H134 Q131 65 122 66 H17 Q12 64 10 60 Z" fill="#b8392d"/>
    <rect x="36" y="42" width="84" height="2.2" fill="#d6b24a"/><rect x="75" y="36" width="2.2" height="7" fill="#d6b24a"/><rect x="80" y="36" width="2.2" height="7" fill="#d6b24a"/>
    <rect x="12" y="27" width="20" height="17" fill="#f4f5f7"/><rect x="14" y="31" width="16" height="2.4" fill="#2e4a6e"/><rect x="14" y="36" width="16" height="2.4" fill="#2e4a6e"/>
    <rect x="16" y="19" width="7" height="8" fill="#d6202f"/><rect x="16" y="19" width="7" height="2.2" fill="#222"/>
    <path d="M118 44 L129 39 L132 44 Z" fill="${hull}"/>
    <path d="M71 17 V29 L77 37" fill="none" stroke="#e5ad00" stroke-width="2.2" stroke-linecap="round"/></svg>`
}
