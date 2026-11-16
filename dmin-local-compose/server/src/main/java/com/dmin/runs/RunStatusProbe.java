package com.dmin.runs;

import com.dmin.system.StatusProbe;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
class RunStatusProbe implements StatusProbe {

    private final RunWorker worker;
    private final AgentClient agent;
    private final RunRepository repo;

    RunStatusProbe(RunWorker worker, AgentClient agent, RunRepository repo) {
        this.worker = worker;
        this.agent = agent;
        this.repo = repo;
    }

    @Override
    public String workerId() {
        return worker.workerId();
    }

    @Override
    public String agentUrl() {
        return agent.url();
    }

    @Override
    public String agentHealth() {
        return agent.health();
    }

    @Override
    public Map<String, Object> counts() {
        return repo.counts();
    }
}
