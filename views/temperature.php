
<?php
//header('Content-type: application/json; charset=utf-8');
$a = "
{
    series:[{
            data:[[0,1],[1,4],[2,3],[3,6],[4,4.5]],
            points:{show:true},
            lines:{show:true}
        },
        [[0,0.5],[1,0.6],[2,1.8],[3,0.9],[4,2]],
        [[0,1.5],[1,2],[2,4.5],[3,3.5],[4,5.5]]
    ],
    options:{
        mouse:{track:true},
        xaxis:{noTicks:10, tickDecimals:0}
    }
}";
echo json_decode($a)."<br>";
echo json_decode(json_encode($data));
?>
