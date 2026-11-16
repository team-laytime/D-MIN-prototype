package com.dmin.system;

import java.util.Map;

/** 실행 쪽(runs 패키지)이 상태 화면에 알려 주는 것. 패키지 사이를 인터페이스 하나로만 잇는다. */
public interface StatusProbe {

    String workerId();

    String agentUrl();

    String agentHealth();

    Map<String, Object> counts();
}
