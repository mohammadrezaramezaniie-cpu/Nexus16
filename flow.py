from pydantic import BaseModel
from crewai import Task, Crew, Process
from crewai.flow.flow import Flow, start, listen
from agents import build_agents


class AgentOSState(BaseModel):
    request: str = ""
    execution_brief: str = ""
    plan: str = ""
    draft: str = ""
    qc: str = ""
    status: str = "NEW"


class AgentOSFlow(Flow[AgentOSState]):
    @start()
    def optimize_intent(self):
        agents = build_agents()
        task = Task(
            description=(
                "Transform the user's request into an execution brief. Preserve intent exactly. "
                "Infer hidden requirements that are necessary to satisfy the request. Include: desired outcome, "
                "constraints, definition of done, acceptance criteria, required evidence/tools and QA method. "
                "If the user names a visual/product reference such as Corva, treat reference fidelity as a hard requirement: "
                "analyze layout grammar, navigation, information density, typography, chart grammar, interaction patterns, "
                "data visualization sophistication and responsive behavior. Do NOT reduce the reference to colors/theme. "
                f"USER REQUEST: {self.state.request}"
            ),
            expected_output="A precise execution brief with measurable acceptance criteria.",
            agent=agents["PO"],
        )
        result = Crew(agents=[agents["PO"]], tasks=[task], process=Process.sequential).kickoff()
        self.state.execution_brief = str(result)
        return self.state.execution_brief

    @listen(optimize_intent)
    def orchestrate(self):
        agents = build_agents()
        task = Task(
            description=(
                "Create the minimal high-quality specialist execution plan for this brief. "
                "Select only needed capability agents from CTX, BUILD, OPP, STR, FIN, LEGAL, RES, DATA, PRES, AUTO. "
                "Always end important work with QC. For app/product work, require independent visual and technical review. "
                f"EXECUTION BRIEF:\n{self.state.execution_brief}"
            ),
            expected_output="Ordered agent plan, dependencies, tools and revision gates.",
            agent=agents["EX"],
        )
        result = Crew(agents=[agents["EX"]], tasks=[task], process=Process.sequential).kickoff()
        self.state.plan = str(result)
        return self.state.plan

    @listen(orchestrate)
    def execute_and_qc(self):
        agents = build_agents()
        execution = Task(
            description=(
                "Execute the request according to the execution brief and plan. "
                "For software/reference-driven UI tasks: research the reference before coding, preserve strong existing architecture, "
                "use real domain-aware data visualization rather than decorative mock charts, and make rendered visual output part of completion. "
                f"BRIEF:\n{self.state.execution_brief}\nPLAN:\n{self.state.plan}"
            ),
            expected_output="Best possible specialist output plus evidence of completion.",
            agent=agents["BUILD"] if any(x in self.state.request.lower() for x in ["app","software","اپ","نرم افزار","سایت","dashboard","داشبورد"]) else agents["RES"],
        )
        qc = Task(
            description=(
                "Independently audit the specialist output against every acceptance criterion in the execution brief. "
                "Do not approve based only on build/tests. For reference-driven software, score Product Fit, UX, Technical Quality, "
                "Visual Quality, DataViz Quality and Reference Fidelity independently. If any hard criterion fails, return FAIL with targeted revisions."
            ),
            expected_output="PASS or FAIL, dimension scores, defects and targeted revision instructions.",
            agent=agents["QC"],
            context=[execution],
        )
        result = Crew(agents=[execution.agent, agents["QC"]], tasks=[execution, qc], process=Process.sequential).kickoff()
        self.state.draft = str(result)
        self.state.qc = str(result)
        self.state.status = "COMPLETED_WITH_QC"
        return result


if __name__ == "__main__":
    import sys
    flow = AgentOSFlow()
    flow.state.request = " ".join(sys.argv[1:]) or "Build a premium industrial application inspired by Corva."
    print(flow.kickoff())
