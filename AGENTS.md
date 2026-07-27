## Everyday paper collection loop practice
### goal
- Create a loop that runs stably, collects papers meeting specific requirements everyday, and summarizes them.

### Structure

/arxiv_paper_loop
  /.claudes
    /agents
      /analyze_pri.toml
       analyze_acc.toml
       theory_deri.toml
       experiment_analyze.toml
    /skills
      /pdf_reader
        SKILL.md
      /arxiv_connect
        SKILL.md
  /.github
    /workflow
      /arxiv_paper_catch.yml
  state.md

#### Introduction
##### subagents
- analyze_pri.toml：Preliminarily screen papers based on abstracts and download them
- analyze_acc.toml：Analyze the paper’s content in detail, including the problem it addresses, the main arguments, the approach to solving the problem, and the paper’s writing logic.
- theory_deri.toml：Analyze the theoretical derivation sections of the paper in detail.
- experiment_analyze.toml：Analyze the experimental part of the paper in detail, including the experimental approach, content, and results.

#### skills
- pdf_reader：help to reading the pdf, including graphs and functions e.g.
- arxiv_connect: to connect arxiv.org