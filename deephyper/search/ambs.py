import signal

from deephyper.search.optimizers import Optimizer
from deephyper.search import Search
from deephyper.search import util

logger = util.conf_logger('deephyper.search.ambs')

SERVICE_PERIOD = 2          # Delay (seconds) between main loop iterations
CHECKPOINT_INTERVAL = 10    # How many jobs to complete between optimizer checkpoints
EXIT_FLAG = False

def on_exit(signum, stack):
    global EXIT_FLAG
    EXIT_FLAG = True

class AMBS(Search):
    def __init__(self):
        super().__init__()
        logger.info("Initializing AMBS")
        self.optimizer = Optimizer(self.problem, self.num_workers, self.args)

    def _extend_parser(self, parser):
        parser.add_argument('--learner',
            default='RF',
            choices=["RF", "ET", "GBRT", "DUMMY", "GP"],
            help='type of learner (surrogate model)'
        )
        parser.add_argument('--liar-strategy',
            default="cl_max",
            choices=["cl_min", "cl_mean", "cl_max"],
            help='Constant liar strategy'
        )
        parser.add_argument('--acq-func',
            default="gp_hedge",
            choices=["LCB", "EI", "PI","gp_hedge"],
            help='Acquisition function type'
        )
        return parser

    def run(self):
        timer = util.DelayTimer(max_minutes=None, period=SERVICE_PERIOD)
        chkpoint_counter = 0
        num_evals = 0

        logger.info(f"Generating {self.num_workers} initial points...")
        XX = self.optimizer.ask_initial(n_points=self.num_workers)
        self.evaluator.add_eval_batch(XX)

        # MAIN LOOP
        for elapsed_str in timer:
            logger.info(f"Elapsed time: {elapsed_str}")
            results = list(self.evaluator.get_finished_evals())
            num_evals += len(results)
            chkpoint_counter += len(results)
            if EXIT_FLAG or num_evals >= self.args.max_evals:
                break
            if results:
                logger.info(f"Refitting model with batch of {len(results)} evals")
                self.optimizer.tell(results)
                logger.info(f"Drawing {len(results)} points with strategy {self.optimizer.strategy}")
                for batch in self.optimizer.ask(n_points=len(results)):
                    self.evaluator.add_eval_batch(batch)
            if chkpoint_counter >= CHECKPOINT_INTERVAL:
                self.evaluator.dump_evals()
                chkpoint_counter = 0

        logger.info('Hyperopt driver finishing')
        self.evaluator.dump_evals()

if __name__ == "__main__":
    search = AMBS()
    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)
    search.run()
